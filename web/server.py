import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config  # noqa: F401  (carrega o .env)
from config.settings import get_settings

STATIC = Path(__file__).parent / "static"

_agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent
    from agents.productivity_agent import criar_agente

    # Monta o agente uma única vez, na subida do servidor, já com as
    # ferramentas nativas + MCP (se configuradas). Evita recarregar tools
    # MCP a cada requisição.
    _agent = await criar_agente()
    yield


app = FastAPI(title="Agente de produtividade", lifespan=lifespan)

_settings = get_settings()
if _settings.cors_origin_list():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_origin_list(),
        allow_methods=["*"],
        allow_headers=["*"],
    )


def get_agent():
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

    esperado = f"Bearer {token}"
    if authorization != esperado:
        raise HTTPException(status_code=401, detail="Token de autenticação inválido ou ausente.")


class ChatIn(BaseModel):
    sessao: str = Field(min_length=1, max_length=64)
    mensagem: str = Field(min_length=1, max_length=4000)


class ResetIn(BaseModel):
    sessao: str = Field(min_length=1, max_length=64)


def _ollama_ok() -> bool:
    settings = get_settings()
    try:
        with urllib.request.urlopen(f"{settings.ollama_base_url}/api/tags", timeout=1.5):
            return True
    except Exception:
        return False


@app.get("/health")
def health():
    """Health check leve para o Render (não depende do Ollama estar de pé)."""
    return {"ok": True}


@app.get("/api/status")
def status():
    settings = get_settings()
    from config.google_auth import token_file

    return {
        "modelo": settings.ollama_model,
        "ollama": _ollama_ok(),
        "google": token_file().exists(),
        "notion": settings.notion_configured(),
        "ambiente": settings.environment,
    }


@app.post("/api/chat", dependencies=[Depends(exigir_autenticacao)])
async def chat(dados: ChatIn):
    try:
        return await run_in_threadpool(get_agent().perguntar, dados.sessao, dados.mensagem)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")


@app.post("/api/reset", dependencies=[Depends(exigir_autenticacao)])
def reset(dados: ResetIn):
    get_agent().limpar(dados.sessao)
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
