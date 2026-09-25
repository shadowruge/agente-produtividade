from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def cliente_e_agente_falso(monkeypatch):
    """Sobe o app substituindo a fábrica do agente (usada no lifespan) por uma
    versão falsa, para não depender de Ollama/MCP reais nem de rede nos testes.
    """
    import agents.productivity_agent as agent_module
    import web.server as server

    agente_falso = MagicMock()
    agente_falso.perguntar.return_value = {"resposta": "Olá!", "ferramentas": []}

    async def _fake_criar_agente():
        return agente_falso

    monkeypatch.setattr(agent_module, "criar_agente", _fake_criar_agente)

    with TestClient(server.app) as cliente:
        yield cliente, agente_falso


def test_health_nao_exige_autenticacao(cliente_e_agente_falso):
    cliente, _ = cliente_e_agente_falso

    resposta = cliente.get("/health")

    assert resposta.status_code == 200
    assert resposta.json() == {"ok": True}


def test_chat_funciona_sem_token_em_desenvolvimento(cliente_e_agente_falso):
    cliente, agente_falso = cliente_e_agente_falso

    resposta = cliente.post("/api/chat", json={"sessao": "s1", "mensagem": "oi"})

    assert resposta.status_code == 200
    assert resposta.json()["resposta"] == "Olá!"
    agente_falso.perguntar.assert_called_once_with("s1", "oi")


def test_chat_exige_token_quando_configurado(cliente_e_agente_falso, monkeypatch):
    cliente, _ = cliente_e_agente_falso
    monkeypatch.setenv("API_AUTH_TOKEN", "segredo123")
    from config.settings import reset_settings_cache

    reset_settings_cache()

    sem_header = cliente.post("/api/chat", json={"sessao": "s1", "mensagem": "oi"})
    assert sem_header.status_code == 401

    com_header = cliente.post(
        "/api/chat",
        json={"sessao": "s1", "mensagem": "oi"},
        headers={"Authorization": "Bearer segredo123"},
    )
    assert com_header.status_code == 200

    com_token_errado = cliente.post(
        "/api/chat",
        json={"sessao": "s1", "mensagem": "oi"},
        headers={"Authorization": "Bearer errado"},
    )
    assert com_token_errado.status_code == 401


def test_producao_sem_token_recusa_chat(cliente_e_agente_falso, monkeypatch):
    cliente, _ = cliente_e_agente_falso
    monkeypatch.setenv("ENVIRONMENT", "production")
    from config.settings import reset_settings_cache

    reset_settings_cache()

    resposta = cliente.post("/api/chat", json={"sessao": "s1", "mensagem": "oi"})

    assert resposta.status_code == 500


def test_reset_limpa_historico(cliente_e_agente_falso):
    cliente, agente_falso = cliente_e_agente_falso

    resposta = cliente.post("/api/reset", json={"sessao": "s1"})

    assert resposta.status_code == 200
    agente_falso.limpar.assert_called_once_with("s1")


def test_chat_valida_payload_vazio(cliente_e_agente_falso):
    cliente, _ = cliente_e_agente_falso

    resposta = cliente.post("/api/chat", json={"sessao": "s1", "mensagem": ""})

    assert resposta.status_code == 422
