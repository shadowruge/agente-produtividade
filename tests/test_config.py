"""Testes da tela de configuração e do armazenamento de segredos.

Cobre os dois bugs que estes módulos resolvem:
- `API_AUTH_TOKEN=` (string vazia, como vem no `.env.example`) era lido
  como token configurado e derrubava todas as requisições com 401.
- A tela precisa funcionar sem nunca devolver o valor de um segredo.
"""

import pytest
from fastapi.testclient import TestClient

from config import secrets_store
from config.settings import get_settings, reset_settings_cache


@pytest.fixture
def config_isolada(monkeypatch, tmp_path):
    """Redireciona o arquivo de configuração para um tmp_path, para os
    testes nunca tocarem no `.config.local.json` do desenvolvedor."""
    arquivo = tmp_path / "config.json"
    monkeypatch.setenv("CONFIG_FILE", str(arquivo))
    monkeypatch.setattr(secrets_store, "caminho", lambda: arquivo)
    reset_settings_cache()
    yield arquivo
    reset_settings_cache()


@pytest.fixture
def sem_env(monkeypatch):
    """Remove variáveis de ambiente para exercitar a precedência do arquivo.

    O `conftest` define todas as variáveis, então sem isto o ambiente
    sempre ganharia e o arquivo nunca seria testado.
    """

    def remover(*nomes: str) -> None:
        for nome in nomes:
            monkeypatch.delenv(nome, raising=False)

    return remover


@pytest.fixture
def cliente(monkeypatch):
    """Cliente com o agente trocado por um dublê: os testes de config não
    devem falar com Ollama nem com a API do Google."""
    from unittest.mock import MagicMock

    import agents.productivity_agent as am
    from web import server

    agente = MagicMock()
    agente.perguntar.return_value = {"resposta": "ok", "ferramentas": []}
    agente.ferramentas = []

    async def fake_criar():
        return agente

    monkeypatch.setattr(am, "criar_agente", fake_criar)
    with TestClient(server.app) as c:
        yield c


# --------------------------------------------------------------------------
# O bug do token vazio
# --------------------------------------------------------------------------


def test_token_vazio_e_tratado_como_nao_configurado(monkeypatch):
    """Este é o bug: o `.env.example` traz `API_AUTH_TOKEN=` (vazio). Se a
    string vazia fosse aceita como token, todo /api/chat responderia 401."""
    monkeypatch.setenv("API_AUTH_TOKEN", "")
    reset_settings_cache()

    settings = get_settings()

    assert settings.api_auth_token is None
    assert settings.is_production() is False


def test_token_vazio_nao_derruba_o_chat(cliente, config_isolada, sessao, monkeypatch):
    """Fim a fim: com API_AUTH_TOKEN vazio, o chat local continua
    funcionando (o comportamento original em desenvolvimento)."""
    monkeypatch.setenv("API_AUTH_TOKEN", "")
    reset_settings_cache()

    r = cliente.post("/api/chat", json={"sessao": sessao, "mensagem": "oi"})

    assert r.status_code == 200, r.text


def test_token_so_com_espacos_tambem_e_vazio(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "   ")
    reset_settings_cache()
    assert get_settings().api_auth_token is None


def test_token_valido_continua_funcionando(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "segredo")
    reset_settings_cache()
    assert get_settings().api_auth_token == "segredo"


# --------------------------------------------------------------------------
# secrets_store
# --------------------------------------------------------------------------


def test_salvar_e_ler(config_isolada):
    secrets_store.salvar({"notion_token": "ntn_abc", "ollama_model": "qwen2.5:7b"})

    dados = secrets_store.ler()
    assert dados["notion_token"] == "ntn_abc"
    assert dados["ollama_model"] == "qwen2.5:7b"


def test_valor_vazio_remove_a_chave(config_isolada):
    """Campo apagado na tela precisa realmente sumir do arquivo."""
    secrets_store.salvar({"notion_token": "ntn_abc"})
    secrets_store.salvar({"notion_token": ""})

    assert "notion_token" not in secrets_store.ler()


def test_limpar_chave(config_isolada):
    secrets_store.salvar({"notion_token": "abc", "ollama_model": "x"})
    secrets_store.limpar_chaves(["notion_token"])

    dados = secrets_store.ler()
    assert "notion_token" not in dados
    assert dados["ollama_model"] == "x"


def test_arquivo_incompreensivel_nao_derruba(config_isolada):
    config_isolada.write_text("isto nao e json", encoding="utf-8")
    assert secrets_store.ler() == {}


def test_arquivo_ausente_devolve_vazio(config_isolada):
    assert secrets_store.ler() == {}


def test_arquivo_fica_com_permissao_0600(config_isolada):
    """Segredos em arquivo legível por outros usuários da máquina seria
    uma falha grave — o arquivo tem que ser 0600."""
    secrets_store.salvar({"notion_token": "segredo"})
    assert oct(config_isolada.stat().st_mode)[-3:] == "600"


def test_salvar_preserva_outros_campos(config_isolada):
    secrets_store.salvar({"notion_token": "abc"})
    secrets_store.salvar({"ollama_model": "llama3"})
    dados = secrets_store.ler()
    assert dados["notion_token"] == "abc"
    assert dados["ollama_model"] == "llama3"


def test_arquivo_nao_e_json_mas_lista(config_isolada):
    config_isolada.write_text("[1, 2, 3]", encoding="utf-8")
    assert secrets_store.ler() == {}


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


def test_le_config_nao_devolve_segredos(cliente, config_isolada):
    """O ponto central do módulo: mesmo com o token salvo, a API responde
    apenas se está configurado."""
    secrets_store.salvar({"notion_token": "ntn_supersecreto", "api_auth_token": "tok_supersecreto"})
    reset_settings_cache()

    # Salvar um api_auth_token passa a exigir autenticação — comportamento
    # fail-closed esperado. Por isso o header vai junto.
    r = cliente.get("/api/config", headers={"Authorization": "Bearer tok_supersecreto"})

    assert r.status_code == 200
    corpo = r.text
    assert "ntn_supersecreto" not in corpo
    assert "tok_supersecreto" not in corpo
    valores = r.json()["valores"]
    assert valores["notion_token"]["configurado"] is True
    assert valores["api_auth_token"]["configurado"] is True


def test_le_config_devolve_valores_nao_secretos(cliente, config_isolada, sem_env):
    sem_env("OLLAMA_MODEL")
    secrets_store.salvar({"ollama_model": "llama3.2"})

    valores = cliente.get("/api/config").json()["valores"]

    assert valores["ollama_model"]["valor"] == "llama3.2"


def test_salvar_config_persiste(cliente, config_isolada):
    r = cliente.post("/api/config", json={"valores": {"notion_token": "ntx", "timezone": "UTC"}})

    assert r.status_code == 200
    dados = secrets_store.ler()
    assert dados["notion_token"] == "ntx"
    assert dados["timezone"] == "UTC"


def test_salvar_config_recarrega_o_agente(cliente, config_isolada, sem_env):
    sem_env("OLLAMA_MODEL")

    r = cliente.post("/api/config", json={"valores": {"ollama_model": "llama3.2"}})

    assert r.status_code == 200
    assert get_settings().ollama_model == "llama3.2"


def test_salvar_ferramentas(cliente, config_isolada):
    r = cliente.post(
        "/api/config",
        json={"ferramentas": ["listar_eventos", "criar_evento"]},
    )

    assert r.status_code == 200
    assert set(get_settings().enabled_tool_list()) == {"listar_eventos", "criar_evento"}


def test_ferramenta_desconhecida_e_rejeitada(cliente, config_isolada):
    r = cliente.post("/api/config", json={"ferramentas": ["tool_inexistente"]})
    assert r.status_code == 422
    assert "tool_inexistente" in r.json()["detail"]


def test_salvar_skills(cliente, config_isolada):
    skills = [{"nome": "agenda", "instrucoes": "Sempre Confirmationar antes de criar."}]

    r = cliente.post("/api/config", json={"skills": skills})

    assert r.status_code == 200
    assert get_settings().skills_list() == skills


def test_campo_desconhecido_e_rejeitado(cliente, config_isolada):
    r = cliente.post("/api/config", json={"valores": {"campo_fake": "x"}})
    assert r.status_code == 422


def test_limpar_campo_desconhecido_e_rejeitado(cliente, config_isolada):
    r = cliente.post("/api/config", json={"limpar": ["campo_fake"]})
    assert r.status_code == 422


def test_config_exige_token_quando_configurado(cliente, config_isolada, monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "segredo123")
    reset_settings_cache()

    assert cliente.get("/api/config").status_code == 401
    assert cliente.post("/api/config", json={"valores": {}}).status_code == 401

    ok = cliente.get("/api/config", headers={"Authorization": "Bearer segredo123"})
    assert ok.status_code == 200


def test_config_sem_token_em_producao_falha_fechado(cliente, config_isolada, monkeypatch):
    """Regra fail-closed: em produção, sem token, a tela que grava as
    chaves de API não pode ficar aberta."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("API_AUTH_TOKEN", "")
    reset_settings_cache()

    assert cliente.get("/api/config").status_code == 500


# --------------------------------------------------------------------------
# Precedência e leitura da tela
# --------------------------------------------------------------------------


def test_ambiente_tem_prioridade_sobre_arquivo(config_isolada, monkeypatch):
    """É o que impede a tela de sobrescrever a configuração real do
    Render, que vem por variável de ambiente."""
    secrets_store.salvar({"ollama_model": "do-arquivo"})
    monkeypatch.setenv("OLLAMA_MODEL", "do-ambiente")
    reset_settings_cache()

    assert get_settings().ollama_model == "do-ambiente"


def test_arquivo_e_usado_quando_ambiente_nao_define(config_isolada, sem_env):
    sem_env("OLLAMA_MODEL")
    secrets_store.salvar({"ollama_model": "do-arquivo"})
    reset_settings_cache()

    assert get_settings().ollama_model == "do-arquivo"


def test_variavel_de_ambiente_vazia_nao_esconde_o_arquivo(config_isolada, monkeypatch):
    """`ENABLED_TOOLS=` num .env de exemplo não pode apagar o que foi salvo
    na tela. Variável vazia = não definida."""
    monkeypatch.setenv("ENABLED_TOOLS", "")
    secrets_store.salvar({"enabled_tools": "criar_nota"})
    reset_settings_cache()

    assert get_settings().enabled_tool_list() == ["criar_nota"]


def test_variavel_de_ambiente_preenchida_vence_o_arquivo(config_isolada, monkeypatch):
    monkeypatch.setenv("ENABLED_TOOLS", "ler_email")
    secrets_store.salvar({"enabled_tools": "criar_nota"})
    reset_settings_cache()

    assert get_settings().enabled_tool_list() == ["ler_email"]


def test_le_config_informa_a_origem_do_valor(cliente, config_isolada, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "do-ambiente")
    reset_settings_cache()

    valores = cliente.get("/api/config").json()["valores"]

    assert valores["ollama_model"]["origem"] == "ambiente"


def test_config_informa_ferramentas_disponiveis(cliente, config_isolada):
    corpo = cliente.get("/api/config").json()

    assert "criar_rascunho" in corpo["ferramentas"]
    assert corpo["habilitadas"] == []  # vazio = todas


def test_pagina_de_config_e_servida(cliente):
    r = cliente.get("/config")
    assert r.status_code == 200
    assert "Configuração do agente" in r.text
