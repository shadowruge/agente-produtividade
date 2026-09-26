import pytest


@pytest.fixture
def cliente_e_agente_falso(cliente_efetivo):
    """Mesma coisa que o fixture `cliente_efetivo` do conftest, com o nome
    antigo que este módulo já usava."""
    return cliente_efetivo


def test_health_nao_exige_autenticacao(cliente):
    resposta = cliente.get("/health")

    assert resposta.status_code == 200
    assert resposta.json() == {"ok": True}


def test_chat_funciona_sem_token_em_desenvolvimento(cliente, sessao, cliente_e_agente_falso):
    _, agente_falso = cliente_e_agente_falso

    resposta = cliente.post("/api/chat", json={"sessao": sessao, "mensagem": "oi"})

    assert resposta.status_code == 200
    assert resposta.json()["resposta"] == "Olá!"
    agente_falso.perguntar.assert_called_once_with(sessao, "oi")


def test_chat_exige_token_quando_configurado(cliente, cliente_e_agente_falso, monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "segredo123")
    from config.settings import reset_settings_cache

    reset_settings_cache()
    # A sessão precisa ser reemitida depois da mudança: o segredo de
    # assinatura deriva do token, então uma sessão emitida antes deixa de
    # valer. É o comportamento correto, não um defeito. E /api/sessao
    # também exige o token, então o header vai junto.
    sessao = cliente.get("/api/sessao", headers={"Authorization": "Bearer segredo123"}).json()[
        "sessao"
    ]

    sem_header = cliente.post("/api/chat", json={"sessao": sessao, "mensagem": "oi"})
    assert sem_header.status_code == 401

    com_header = cliente.post(
        "/api/chat",
        json={"sessao": sessao, "mensagem": "oi"},
        headers={"Authorization": "Bearer segredo123"},
    )
    assert com_header.status_code == 200

    com_token_errado = cliente.post(
        "/api/chat",
        json={"sessao": sessao, "mensagem": "oi"},
        headers={"Authorization": "Bearer errado"},
    )
    assert com_token_errado.status_code == 401


def test_sessao_emitida_antes_do_token_deixa_de_valer(cliente, sessao, monkeypatch):
    """Trocar o token invalida as sessões em voo — é o que impede que um
    token revogado continue dando acesso a conversas antigas."""
    monkeypatch.setenv("API_AUTH_TOKEN", "segredo123")
    from config.settings import reset_settings_cache

    reset_settings_cache()

    r = cliente.post("/api/chat", json={"sessao": sessao, "mensagem": "oi"})

    assert r.status_code == 401


def test_producao_sem_token_recusa_chat(cliente, sessao, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    from config.settings import reset_settings_cache

    reset_settings_cache()

    resposta = cliente.post("/api/chat", json={"sessao": sessao, "mensagem": "oi"})

    assert resposta.status_code == 500


def test_reset_limpa_historico(cliente, sessao, cliente_e_agente_falso):
    _, agente_falso = cliente_e_agente_falso

    resposta = cliente.post("/api/reset", json={"sessao": sessao})

    assert resposta.status_code == 200
    agente_falso.limpar.assert_called_once_with(sessao)


def test_chat_valida_payload_vazio(cliente, sessao):
    resposta = cliente.post("/api/chat", json={"sessao": sessao, "mensagem": ""})

    assert resposta.status_code == 422
