"""Configuração persistente do agente, gravada fora do git.

O objetivo é permitir configurar o agente pela interface web
(`web/static/config.html`) sem precisar escrever — nem versionar — um
arquivo `.env`.

Decisões de segurança (leia antes de mexer):

- O arquivo fica na raiz do projeto, fora do git (ver `.gitignore`) e é
  criado com permissão `0600` (só o dono lê/escreve). A gravação é
  atômica: escreve num `.tmp` e substitui, para nunca deixar o arquivo
  pela metade.
- A API web nunca devolve o valor de um segredo. Ela responde apenas se
  ele está "configurado" ou não. Segredos são *write-only* pela interface:
  você digita o valor uma vez e nunca mais consegue lê-lo pela tela. Isso
  é proposital — se o endpoint devolvesse o valor, qualquer pessoa com
  acesso ao servidor (ou um XSS) teria as chaves.
- Variáveis de ambiente reais têm prioridade sobre este arquivo (ver
  `config/settings.py`). É assim que o Render injeta as chaves em
  produção, e é o que impede a tela de sobrescrever a configuração real do
  serviço.
- Este módulo NÃO importa `config.settings`, de propósito: `settings` usa
  este arquivo como fonte de configuração, e a importação criaria um
  ciclo. Por isso o caminho do arquivo é lido direto do ambiente.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

ARQUIVO_PADRAO = ".config.local.json"


def caminho() -> Path:
    """Caminho do arquivo de configuração. Lido do ambiente, sem pydantic,
    para evitar ciclo de importação com `config.settings`."""
    return ROOT / os.getenv("CONFIG_FILE", ARQUIVO_PADRAO)


# --------------------------------------------------------------------------
# Schema: a tela de configuração é desenhada a partir disto
# --------------------------------------------------------------------------
# `nome`    -> campo em config/settings.py
# `segredo` -> True = write-only (nunca devolvido pela API)
#
# Ao adicionar um campo aqui, adicione também em `config/settings.py`.

CAMPOS: list[dict[str, Any]] = [
    # --- Modelo de IA ---
    {
        "nome": "ollama_model",
        "rotulo": "Modelo do Ollama",
        "grupo": "modelo",
        "tipo": "texto",
        "segredo": False,
        "ajuda": "Ex.: qwen2.5:7b. Confira com 'ollama list'.",
    },
    {
        "nome": "ollama_base_url",
        "rotulo": "URL do Ollama",
        "grupo": "modelo",
        "tipo": "texto",
        "segredo": False,
        "ajuda": "Ex.: http://localhost:11434. Em produção, a URL de um Ollama acessível pela internet.",
    },
    {
        "nome": "timezone",
        "rotulo": "Fuso horário",
        "grupo": "modelo",
        "tipo": "texto",
        "segredo": False,
        "ajuda": "Ex.: America/Sao_Paulo. Usado na agenda e na data/hora do agente.",
    },
    # --- Google ---
    {
        "nome": "google_credentials_file",
        "rotulo": "Arquivo de credenciais do Google",
        "grupo": "google",
        "tipo": "texto",
        "segredo": False,
        "ajuda": "Nome do credentials.json, na raiz do projeto. Rode 'python main.py --auth' para gerar o token.",
    },
    {
        "nome": "google_token_file",
        "rotulo": "Arquivo de token do Google",
        "grupo": "google",
        "tipo": "texto",
        "segredo": False,
        "ajuda": "Nome do token.json, na raiz do projeto.",
    },
    # --- Notion ---
    {
        "nome": "notion_token",
        "rotulo": "Notion token",
        "grupo": "notion",
        "tipo": "segredo",
        "segredo": True,
        "ajuda": "Em notion.so/my-integrations → sua integração → Segredos → Show.",
    },
    {
        "nome": "notion_database_id",
        "rotulo": "ID do banco do Notion",
        "grupo": "notion",
        "tipo": "texto",
        "segredo": False,
        "ajuda": "Os 32 caracteres do banco na URL, antes do '?v='.",
    },
    {
        "nome": "notion_title_prop",
        "rotulo": "Coluna de título do Notion",
        "grupo": "notion",
        "tipo": "texto",
        "segredo": False,
        "ajuda": "Nome exato da coluna de título do banco (ex.: Nome, Name, Título).",
    },
    # --- MCP ---
    {
        "nome": "mcp_servers",
        "rotulo": "Servidores MCP (JSON)",
        "grupo": "mcp",
        "tipo": "area",
        "segredo": False,
        "ajuda": 'Opcional. Ex.: {"clima":{"transport":"streamable_http","url":"https://exemplo.com/mcp"}}',
    },
    # --- Segurança ---
    {
        "nome": "api_auth_token",
        "rotulo": "Token de acesso à API",
        "grupo": "seguranca",
        "tipo": "segredo",
        "segredo": True,
        "ajuda": "Exigido em /api/chat, /api/reset e /api/config. Gere com: openssl rand -hex 32",
    },
    {
        "nome": "cors_origins",
        "rotulo": "Origens liberadas (CORS)",
        "grupo": "seguranca",
        "tipo": "texto",
        "segredo": False,
        "ajuda": "Separadas por vírgula. Deixe vazio se a interface for servida pelo mesmo domínio da API.",
    },
]

CAMPOS_SENHETAIS: frozenset[str] = frozenset(c["nome"] for c in CAMPOS if c["segredo"])
CAMPOS_VALIDOS: frozenset[str] = frozenset(c["nome"] for c in CAMPOS)


# --------------------------------------------------------------------------
# Leitura / escrita
# --------------------------------------------------------------------------


def ler() -> dict[str, str]:
    """Lê o arquivo de configuração. Retorna {} se não existir ou estiver
    corrompido — um arquivo inválido não deve derrubar o servidor."""
    arquivo = caminho()
    if not arquivo.exists():
        return {}
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(dados, dict):
        return {}
    return {str(k): str(v) for k, v in dados.items() if isinstance(v, (str, int, float))}


def salvar(valores: dict[str, str]) -> None:
    """Mescla `valores` no arquivo existente e grava de forma atômica com
    permissão 0600. Campos com valor vazio são removidos, para que "apagar
    o campo" na tela realmente limpe a configuração."""
    atual = ler()
    for chave, valor in valores.items():
        if valor is None or not str(valor).strip():
            atual.pop(chave, None)
        else:
            atual[chave] = str(valor).strip()
    _gravar_atomico(atual)


def limpar_chaves(chaves: list[str]) -> None:
    """Remove chaves do arquivo (usado pelo botão 'apagar' da tela)."""
    if not chaves:
        return
    atual = ler()
    mudou = False
    for chave in chaves:
        if atual.pop(chave, None) is not None:
            mudou = True
    if mudou:
        _gravar_atomico(atual)


def _gravar_atomico(dados: dict[str, str]) -> None:
    """Grava o arquivo de forma atômica, sempre com permissão 0600.

    Escreve num `.tmp` e substitui o destino com `replace`, que no POSIX é
    atômico: um leitor nunca vê o arquivo pela metade, nem um crash no meio
    da escrita deixa a configuração do agente corrompida.
    """
    arquivo = caminho()
    tmp = arquivo.with_name(arquivo.name + ".tmp")
    # O_EXCL não é usado de propósito: queremos sobrescrever um .tmp preso
    # de uma gravação anterior interrompida.
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(dados, fh, indent=2, ensure_ascii=False, sort_keys=True)
            fh.write("\n")
        # Reforça a permissão: se o .tmp já existia, o O_CREAT acima não
        # reaplica o modo.
        tmp.chmod(0o600)
        tmp.replace(arquivo)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def mascarar(chaves: list[str]) -> dict[str, dict[str, Any]]:
    """Monta o resumo seguro de um conjunto de campos para a API: em vez do
    valor, diz apenas se está configurado."""
    atual = ler()
    return {
        chave: {
            "configurado": bool(atual.get(chave, "").strip()),
            "origem": "arquivo",
        }
        for chave in chaves
    }
