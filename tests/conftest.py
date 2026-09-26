from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from config import secrets_store
from config.settings import get_settings, reset_settings_cache


@pytest.fixture(autouse=True)
def _env_base(monkeypatch, tmp_path):
    """Ambiente mínimo e isolado para cada teste.

    Garante que nenhum teste dependa do .env real do desenvolvedor, do
    arquivo de configuração local (.config.local.json) ou do cache de
    Settings (lru_cache).
    """
    # Definimos cada variável explicitamente (em vez de só apagar) porque um
    # eventual .env real do projeto (na raiz) também seria lido pelo
    # pydantic-settings; variáveis de ambiente do processo têm prioridade
    # sobre o .env, então isso garante testes determinísticos.
    padrao = {
        "ENVIRONMENT": "development",
        "HOST": "127.0.0.1",
        "PORT": "8000",
        "API_AUTH_TOKEN": "",
        "OLLAMA_MODEL": "qwen2.5:7b",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "TIMEZONE": "America/Sao_Paulo",
        "GOOGLE_CREDENTIALS_FILE": "credentials.json",
        "GOOGLE_TOKEN_FILE": "token.json",
        "NOTION_TOKEN": "",
        "NOTION_DATABASE_ID": "",
        "NOTION_TITLE_PROP": "Name",
        "MCP_SERVERS": "",
        "CORS_ORIGINS": "",
        "ENABLED_TOOLS": "",
        "SKILLS": "",
    }
    for var, valor in padrao.items():
        monkeypatch.setenv(var, valor)
    # api_auth_token é opcional (str | None, default None) e não existe no
    # .env real do projeto, então remover do ambiente já cai no default.
    # NOTION_TOKEN/NOTION_DATABASE_ID, por outro lado, normalmente existem
    # no .env real do desenvolvedor — por isso ficam como "" (setado acima,
    # não removido), o que também é "falsy" para notion_configured().
    monkeypatch.delenv("API_AUTH_TOKEN", raising=False)

    # Config.Isso é essencial: sem apontar para um arquivo inexistente, o
    # .config.local.json real do desenvolvedor (escrito pela tela de
    # configuração) entraria nos testes e os tornaria dependentes da
    # máquina de quem roda.
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "config-inexistente.json"))
    monkeypatch.setattr(secrets_store, "caminho", lambda: tmp_path / "config-inexistente.json")

    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def cliente_efetivo():
    """Cliente HTTP com o agente substituído por um dublê.

    Falar com Ollama, Google ou Notion de verdade não cabe em teste de
    API. É função (e não um simples `with`) para poder entrar como
    dependência de outros fixtures, como o `sessao`.
    """
    from unittest.mock import MagicMock

    import agents.productivity_agent as am
    from web import server

    agente = MagicMock()
    agente.perguntar.return_value = {"resposta": "Olá!", "ferramentas": []}
    agente.ferramentas = []

    async def fake_criar_agente():
        return agente

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(am, "criar_agente", fake_criar_agente)
        with TestClient(server.app) as cliente:
            yield cliente, agente


@pytest.fixture
def cliente(cliente_efetivo):
    """Cliente HTTP com agente falso, para quando o teste não precisa do
    dublê em si."""
    return cliente_efetivo[0]


@pytest.fixture
def sessao(cliente):
    """Um id de sessão válido, emitido pelo endpoint — o mesmo caminho que o
    navegador usa.

    Desde a adoção das sessões assinadas, /api/chat e /api/reset recusam
    qualquer id que o cliente tenha inventado. Os testes precisam de um id
    de verdade, e não devem forjar a assinatura para isso, senão a proteção
    nem estaria sendo testada.
    """
    return cliente.get("/api/sessao").json()["sessao"]


@pytest.fixture
def mock_google_service(monkeypatch):
    """Substitui get_service (já importado) nos módulos de tools que o usam,
    devolvendo um MagicMock que cada teste configura conforme o esperado.
    """
    servico = MagicMock()
    monkeypatch.setattr("tools.google_calendar.get_service", lambda *a, **k: servico)
    monkeypatch.setattr("tools.gmail.get_service", lambda *a, **k: servico)
    return servico


@pytest.fixture
def mock_notion_client(monkeypatch):
    """Substitui get_client (já importado) em tools.notion_tools."""
    cliente = MagicMock()
    monkeypatch.setattr("tools.notion_tools.get_client", lambda: cliente)
    monkeypatch.setenv("NOTION_TOKEN", "token-fake")
    monkeypatch.setenv("NOTION_DATABASE_ID", "database-fake")
    return cliente
