import json
import os
import secrets as pysecrets
import time
import urllib.request
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Importa o pacote config por efeito colateral: é ele que carrega o .env.
import config  # noqa: F401
from config import secrets_store
from config.settings import get_settings
from tools import BASE_TOOLS

STATIC = Path(__file__).parent / "static"

_agent = None


@asynccontextmanager
# `app` é exigido pela assinatura do lifespan do FastAPI e não é usado:
# o agente é global por desenho (ver `recarregar_agente`).
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: ARG001
    global _agent
    from agents.productivity_agent import criar_agente

    # Monta o agente uma única vez, na subida do servidor, já com as
    # ferramentas nativas + MCP (se configuradas). Evita recarregar tools
    # MCP a cada requisição.
    _agent = await criar_agente()
    yield
    _agent = None


async def recarregar_agente() -> None:
    """Remonta o agente. Usado depois de salvar a configuração, para que
    modelo, ferramentas e skills novos valham sem reiniciar o servidor.

    Histórico de conversas é descartado de propósito: as ferramentas podem
    ter mudado e o histórico antigo não faria sentido para o agente novo.
    """
    global _agent
    from agents.productivity_agent import criar_agente

    _agent = await criar_agente()


app = FastAPI(title="Agente de produtividade", lifespan=lifespan)

_settings = get_settings()
if _settings.cors_origin_list():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_origin_list(),
        allow_methods=["*"],
        allow_headers=["*"],
    )


def get_agent() -> Any:
    if _agent is None:
        # Salvaguarda: se por algum motivo o lifespan não rodou (ex: testes
        # chamando a função diretamente), cria o agente de forma síncrona
        # com as ferramentas nativas (sem MCP).
        from agents.productivity_agent import ProductivityAgent

        return ProductivityAgent()
    return _agent


def exigir_autenticacao(authorization: str | None = Header(default=None)) -> None:
    """Protege os endpoints /api/*.

    Se API_AUTH_TOKEN não estiver definido, e o ambiente for
    "development", o acesso é liberado (comportamento local, igual ao
    projeto original). Em produção (ENVIRONMENT=production), um token é
    obrigatório: sem ele, qualquer pessoa com a URL pública do Render
    conseguiria ler e-mails, mexer na agenda e criar notas.
    """
    settings = get_settings()
    token = settings.api_auth_token

    if token is None:
        if settings.is_production():
            raise HTTPException(
                status_code=500,
                detail="API_AUTH_TOKEN não configurado. Defina essa variável de "
                "ambiente antes de expor o serviço em produção.",
            )
        return  # dev local sem token: mantém o comportamento original

    # compare_digest, não `!=`: comparar segredo com `==` vaza informação
    # por tempo de execução. Barato de fazer certo.
    esperado = f"Bearer {token}"
    if not authorization or not pysecrets.compare_digest(authorization, esperado):
        raise HTTPException(status_code=401, detail="Token de autenticação inválido ou ausente.")


class ChatIn(BaseModel):
    # 96 = 24 chars de nonce em base64url + "." + 32 de assinatura.
    sessao: str = Field(min_length=1, max_length=96)
    mensagem: str = Field(min_length=1, max_length=4000)


class ResetIn(BaseModel):
    sessao: str = Field(min_length=1, max_length=96)


def exigir_sessao(dados: ChatIn | ResetIn) -> str:
    """Valida a assinatura do id de sessão.

    Um id forjado (ou copiado da rede) é recusado: sem isso, qualquer
    cliente que descobrisse o id de outra pessoa leria o histórico dela.
    Ver `config/sessoes.py` para o motivo e para o que isto não resolve.
    """
    from config import sessoes

    sessao = sessoes.validar(dados.sessao)
    if sessao is None:
        raise HTTPException(
            status_code=401,
            detail="Sessão inválida. Recarregue a página para obter uma nova.",
        )
    return sessao


class ConfigIn(BaseModel):
    """Payload da tela de configuração.

    `valores` só aceita os nomes declarados em `secrets_store.CAMPOS`
    (validado no endpoint). Segredos vêm preenchidos só quando o usuário
    digitou algo novo; campo ausente = mantém o que já estava salvo.
    """

    valores: dict[str, str] = Field(default_factory=dict)
    limpar: list[str] = Field(default_factory=list, max_length=40)
    ferramentas: list[str] | None = None
    skills: list[dict[str, str]] | None = None


def _ollama_ok() -> bool:
    """Sonda o Ollama para o ponto de status.

    O `except Exception` é deliberado: o objetivo é exatamente não saber
    *por que* a chamada falhou. Connection refused, DNS, timeout, HTTP
    500 — todos significam a mesma coisa aqui: "ponto vermelho". Uma
    exceção desconhecida também não deve derrubar o /api/status inteiro.
    """
    settings = get_settings()
    try:
        # URL vinda da configuração, não de entrada do usuário: o destino
        # é o Ollama que o operador configurou. Bandit accuses urlopen com
        # URL variável, o que aqui não se aplica.
        with urllib.request.urlopen(  # noqa: S310
            f"{settings.ollama_base_url}/api/tags", timeout=1.5
        ):
            return True
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------
# Limite de requisições
# --------------------------------------------------------------------------
# Cada /api/chat ocupa uma thread do threadpool por uma chamada longa de
# LLM (com até 6 iterações de ferramentas). Sem teto, um cliente disparando
# requisições enche a fila e derruba o chat para todo mundo. É um limite
# simples em memória: suficiente para uso pessoal, que é o caso do projeto.
MAX_CHAT_POR_MINUTO = 20
# Teto de IPs rastreados. Um LRU de verdade: sem ele, um cliente distribuindo
# requisições por muitos IPs (ou atrás de um proxy) faria este dicionário
# crescer sem limite, já que nada estaria "antigo" o bastante para sair.
MAX_IPS_RASTREADOS = 1024
_chats: OrderedDict[str, list[float]] = OrderedDict()


def _limpar_ips_antigos(agora: float) -> None:
    for chave in [k for k, v in _chats.items() if not v or agora - v[-1] >= 60]:
        _chats.pop(chave, None)


def limitar_chat(request: Request) -> None:
    agora = time.monotonic()
    ip = request.client.host if request.client else "desconhecido"
    com_ip = [t for t in _chats.get(ip, []) if agora - t < 60]

    if len(com_ip) >= MAX_CHAT_POR_MINUTO:
        _chats[ip] = com_ip
        raise HTTPException(
            status_code=429,
            detail=f"Muitas mensagens seguidas. Aguarde um pouco (limite de "
            f"{MAX_CHAT_POR_MINUTO} por minuto).",
        )

    com_ip.append(agora)
    _chats[ip] = com_ip
    _chats.move_to_end(ip)

    _limpar_ips_antigos(agora)
    # Ainda acima do teto? descarta os IPs menos usados recentemente.
    while len(_chats) > MAX_IPS_RASTREADOS:
        _chats.popitem(last=False)


@app.get("/health")
def health() -> dict[str, bool]:
    """Health check leve para o Render (não depende do Ollama estar de pé)."""
    return {"ok": True}


@app.get("/api/status", dependencies=[Depends(exigir_autenticacao)])
def status() -> dict[str, Any]:
    settings = get_settings()
    from config.google_auth import token_file

    return {
        "modelo": settings.ollama_model,
        "ollama": _ollama_ok(),
        "google": token_file().exists(),
        "notion": settings.notion_configured(),
        "ambiente": settings.environment,
        "ferramentas": [t.name for t in get_agent().ferramentas],
    }


@app.get("/api/sessao", dependencies=[Depends(exigir_autenticacao)])
def nova_sessao() -> dict[str, str]:
    """Emite um id de sessão assinado.

    O navegador pede um na primeira visita e guarda no sessionStorage. O id
    vai no corpo das chamadas de chat, então um cliente que inventa o
    próprio valor é simplesmente recusado.
    """
    from config import sessoes

    return {"sessao": sessoes.emitir()}


@app.post(
    "/api/chat",
    dependencies=[Depends(exigir_autenticacao), Depends(limitar_chat)],
)
async def chat(dados: ChatIn) -> dict[str, Any]:
    sessao = exigir_sessao(dados)
    try:
        return await run_in_threadpool(get_agent().perguntar, sessao, dados.mensagem)
    except Exception as exc:
        # Lastro de verdade: aqui uma falha de uma tool (Google, Notion,
        # MCP) não pode virar 500 genérico sem dizer o que houve. O
        # `except` é amplo porque a lista de causas é aberta (rede,
        # OAuth, LangChain, tools de terceiros) e todas precisam virar
        # uma mensagem legível.
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@app.post("/api/reset", dependencies=[Depends(exigir_autenticacao)])
def reset(dados: ResetIn) -> dict[str, bool]:
    get_agent().limpar(exigir_sessao(dados))
    return {"ok": True}


# --------------------------------------------------------------------------
# Tela de configuração
# --------------------------------------------------------------------------
# Mesmo esquema de `exigir_autenticacao` para /api/config: liberada em
# desenvolvimento sem token, obrigatória em produção. A diferença é que
# aqui a proteção importa mais — este endpoint grava as chaves de API.
@app.get("/api/config", dependencies=[Depends(exigir_autenticacao)])
def ler_config() -> dict[str, Any]:
    """Devolve a configuração atual. Segredos NÃO são devolvidos: apenas se
    estão configurados. É por isso que o campo aparece como 'salvo' e não
    preenchido."""
    settings = get_settings()
    arquivo = secrets_store.ler()

    valores: dict[str, object] = {}
    for campo in secrets_store.CAMPOS:
        nome = campo["nome"]
        if campo["segredo"]:
            valores[nome] = {
                "configurado": bool(str(arquivo.get(nome, "")).strip()),
                "origem": _origem(nome),
            }
        else:
            valores[nome] = {
                "valor": str(getattr(settings, nome, "")),
                "origem": _origem(nome),
            }

    return {
        "campos": secrets_store.CAMPOS,
        "valores": valores,
        "ferramentas": [t.name for t in BASE_TOOLS],
        "habilitadas": settings.enabled_tool_list(),
        "skills": settings.skills_list(),
        "ambiente": settings.environment,
        "arquivo": str(secrets_store.caminho().name),
    }


def _origem(nome: str) -> str:
    """De onde veio o valor efetivo: ambiente, arquivo local ou padrão.

    Ajuda a responder 'por que meu valor não mudou?': quase sempre é uma
    variável de ambiente do Render, que tem prioridade por design.
    """
    if os.getenv(nome.upper()):
        return "ambiente"
    if str(secrets_store.ler().get(nome, "")).strip():
        return "arquivo"
    return "padrao"


@app.post("/api/config", dependencies=[Depends(exigir_autenticacao)])
async def salvar_config(dados: ConfigIn) -> dict[str, Any]:
    from config import sessoes
    from config.settings import reset_settings_cache

    desconhecidos = set(dados.valores) - secrets_store.CAMPOS_VALIDOS
    if desconhecidos:
        raise HTTPException(
            status_code=422,
            detail=f"Campo(s) desconhecido(s): {', '.join(sorted(desconhecidos))}",
        )
    if set(dados.limpar) - secrets_store.CAMPOS_VALIDOS:
        raise HTTPException(status_code=422, detail="Não é possível limpar esse campo.")

    secrets_store.salvar(dados.valores)
    secrets_store.limpar_chaves(dados.limpar)
    sessoes._cache_resetado()  # o token novo muda o segredo das sessões

    extras: dict[str, str] = {}
    if dados.ferramentas is not None:
        validas = {t.name for t in BASE_TOOLS}
        invalidas = set(dados.ferramentas) - validas
        if invalidas:
            raise HTTPException(
                status_code=422,
                detail=f"Ferramenta desconhecida: {', '.join(sorted(invalidas))}",
            )
        extras["enabled_tools"] = ",".join(dados.ferramentas)
    if dados.skills is not None:
        extras["skills"] = json.dumps(dados.skills, ensure_ascii=False)

    if extras:
        secrets_store.salvar(extras)

    reset_settings_cache()
    await recarregar_agente()
    return {"ok": True, "mensagem": "Configuração salva. O agente foi recarregado."}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/config")
def config_page() -> FileResponse:
    return FileResponse(STATIC / "config.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
