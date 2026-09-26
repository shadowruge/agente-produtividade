"""Testes do limite de requisições e da proteção dos endpoints /api.

O rate limit existe porque cada /api/chat segura uma thread do threadpool
por uma chamada longa de LLM: sem teto, um cliente disparando requisições
enche a fila e derruba o chat para todo mundo.
"""

import pytest
from fastapi import HTTPException

from web import server
from web.server import MAX_CHAT_POR_MINUTO


@pytest.fixture(autouse=True)
def limpa_contadores():
    server._chats.clear()
    yield
    server._chats.clear()


def _chat(cliente, sessao, mensagem="oi"):
    return cliente.post("/api/chat", json={"sessao": sessao, "mensagem": mensagem})


def test_chat_ate_o_limite_passa(cliente, sessao):
    for i in range(MAX_CHAT_POR_MINUTO):
        r = _chat(cliente, sessao, f"msg{i}")
        assert r.status_code == 200, f"falhou na mensagem {i}"


def test_chat_alem_do_limite_e_recusado(cliente, sessao):
    for _ in range(MAX_CHAT_POR_MINUTO):
        _chat(cliente, sessao)

    r = _chat(cliente, sessao, "mais uma")

    assert r.status_code == 429
    assert "minuto" in r.json()["detail"]


def test_requisicoes_antigas_sao_esquecidas(cliente, sessao, monkeypatch):
    """Passados 60s, o contador zera — o limite é de janela, não de vida
    toda do processo."""
    agora = 1000.0
    monkeypatch.setattr(server.time, "monotonic", lambda: agora)

    for _ in range(MAX_CHAT_POR_MINUTO):
        _chat(cliente, sessao)
    assert _chat(cliente, sessao).status_code == 429

    agora += 61
    assert _chat(cliente, sessao).status_code == 200


def test_limite_nao_afeta_outros_endpoints(cliente, sessao):
    """Só /api/chat é limitado; /api/reset e /api/config continuam."""
    for _ in range(MAX_CHAT_POR_MINUTO + 5):
        _chat(cliente, sessao)

    assert cliente.get("/api/status").status_code == 200
    assert cliente.post("/api/reset", json={"sessao": sessao}).status_code == 200


def _req(ip):
    from types import SimpleNamespace

    return SimpleNamespace(client=SimpleNamespace(host=ip))


def test_outro_cliente_nao_e_afetado():
    """O limite é por IP: um cliente não pode travar os outros.

    Testa a função direto, com hosts diferentes — pelo TestClient todos
    viriam do mesmo host e o teste não provaria nada.
    """
    for _ in range(MAX_CHAT_POR_MINUTO):
        server.limitar_chat(_req("10.0.0.1"))

    with pytest.raises(HTTPException) as ex:
        server.limitar_chat(_req("10.0.0.1"))
    assert ex.value.status_code == 429

    server.limitar_chat(_req("10.0.0.2"))  # IP diferente passa


def test_contador_nao_cresce_sem_limite():
    """O mesmo vazamento corrigido no histórico não pode existir aqui: com
    muitos IPs ativos, nada ficaria 'antigo' o bastante para ser removido."""
    for i in range(1200):
        server.limitar_chat(_req(f"10.0.{i // 250}.{i % 250}"))

    assert len(server._chats) <= 1024


def test_status_exige_autenticacao(cliente, monkeypatch):
    """/api/status diz se há token do Google e se o Notion está pronto:
    informação que não deveria ser pública em produção."""
    from config.settings import reset_settings_cache

    monkeypatch.setenv("API_AUTH_TOKEN", "segredo")
    reset_settings_cache()

    assert cliente.get("/api/status").status_code == 401
    assert (
        cliente.get("/api/status", headers={"Authorization": "Bearer segredo"}).status_code == 200
    )


def test_health_nunca_exige_autenticacao(cliente, monkeypatch):
    """O Render precisa do /health para decidir se o serviço está vivo."""
    from config.settings import reset_settings_cache

    monkeypatch.setenv("API_AUTH_TOKEN", "segredo")
    reset_settings_cache()

    assert cliente.get("/health").status_code == 200


def test_comparacao_de_token_nao_vaza_tempo():
    """A comparação precisa ser constante; um `==` ingênuo já foi um estouro
    aqui. Este teste trava a intenção."""
    import inspect

    src = inspect.getsource(server.exigir_autenticacao)
    assert "compare_digest" in src
    assert "authorization != esperado" not in src
