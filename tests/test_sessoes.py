"""Testes das sessões assinadas.

O problema que isto resolve: sem assinatura, qualquer cliente que
adivinhasse ou copiasse o id de sessão de outra pessoa leria o histórico
dela — que é onde ficam o que o agente descobriu da agenda e dos e-mails.
"""

import pytest

from config import sessoes


@pytest.fixture(autouse=True)
def isola_segredo():
    """Cada teste começa com o cache de derivadas limpo e o segredo local
    zerado, senão o estado vazaria entre testes."""
    sessoes._cache_resetado()
    sessoes._segredo_local = None
    yield
    sessoes._cache_resetado()
    sessoes._segredo_local = None


# --------------------------------------------------------------------------
# Emissão e validação
# --------------------------------------------------------------------------


def test_sessao_emitida_e_aceita():
    s = sessoes.emitir()
    assert sessoes.validar(s) == s


def test_sessoes_sao_distintas():
    ids = {sessoes.emitir() for _ in range(50)}
    assert len(ids) == 50


def test_nao_tem_nonce_legivel_em_comum():
    """O nonce tem entropia suficiente: é o que dispensa um KDF caro na
    assinatura."""
    nonces = {s.split(".")[0] for s in (sessoes.emitir() for _ in range(50))}
    assert len(nonces) == 50
    assert all(len(n) >= 30 for n in nonces)


@pytest.mark.parametrize(
    "entrada",
    ["", "sem-ponto", ".so-assinatura", "nonce.", "nonce.assinatura-errada", None],
)
def test_entradas_invalidas_sao_recusadas(entrada):
    assert sessoes.validar(entrada) is None


def test_assinatura_adulterada_e_recusada():
    """O ataque real: o cliente pega uma sessão válida (a dele ou vista na
    rede) e mexe em um caractere da assinatura."""
    s = sessoes.emitir()
    nonce, _, assinatura = s.partition(".")
    adulterada = "a" + assinatura[1:] if assinatura[0] != "a" else "b" + assinatura[1:]

    assert sessoes.validar(f"{nonce}.{adulterada}") is None


def test_nonce_trocado_com_assinatura_valida_e_recusado():
    """Não basta ter uma assinatura qualquer: ela precisa ser a do nonce
    específico. Uma assinatura de outra sessão não pode ser reaproveitada."""
    a = sessoes.emitir()
    b = sessoes.emitir()
    nonce_a, _, assinatura_a = a.partition(".")

    assert sessoes.validar(f"{nonce_a}.{assinatura_a}") == a
    # A mesma assinatura num nonce diferente não vale nada.
    assert sessoes.validar(b) == b
    assert sessoes.validar(b.replace(b.split(".")[1], assinatura_a, 1)) is None


# --------------------------------------------------------------------------
# Ligação com o token de API
# --------------------------------------------------------------------------


def test_trocar_o_token_invalida_as_sessoes_antigas(monkeypatch):
    """É o que impede que um token revogado continue abrindo conversas já
    existentes."""
    from config.settings import reset_settings_cache

    monkeypatch.setenv("API_AUTH_TOKEN", "token-antigo")
    reset_settings_cache()
    sessoes._cache_resetado()
    antiga = sessoes.emitir()
    assert sessoes.validar(antiga) == antiga

    monkeypatch.setenv("API_AUTH_TOKEN", "token-novo")
    reset_settings_cache()
    sessoes._cache_resetado()

    assert sessoes.validar(antiga) is None


def test_sem_token_usa_segredo_aleatorio(monkeypatch):
    """Em desenvolvimento não há token; as sessões usam um segredo do
    processo. Dois "servidores" com segredos distintos não aceitam a mesma
    sessão um do outro."""
    from config.settings import reset_settings_cache

    monkeypatch.delenv("API_AUTH_TOKEN", raising=False)
    reset_settings_cache()
    s = sessoes.emitir()

    outro = sessoes.emitir()
    assert s != outro
    assert sessoes.validar(s) is not None


def test_validar_e_rapido_sem_kdf(monkeypatch):
    """Um KDF caro aqui viraria vetor de negação de serviço: cada
    validação custaria dezenas de ms de CPU, disparáveis à vontade.
    Este teste trava a decisão de manter HMAC simples."""
    import time

    s = sessoes.emitir()

    inicio = time.perf_counter()
    for _ in range(200):
        sessoes.validar(s)
    decorrido = time.perf_counter() - inicio

    # 200 validações em menos de meio segundo; com PBKDF2 a 80k it'd, seriam
    # vários segundos.
    assert decorrido < 0.5, f"validacao lenta demais: {decorrido:.3f}s para 200 chamadas"


# --------------------------------------------------------------------------
# Endpoint
# --------------------------------------------------------------------------


def test_endpoint_emite_sessao_valida(cliente):
    r = cliente.get("/api/sessao")

    assert r.status_code == 200
    s = r.json()["sessao"]
    assert sessoes.validar(s) == s


def test_chat_recusa_sessao_forjada(cliente):
    """O caminho que fecha o ataque: um id inventado pelo cliente é
    rejeitado antes de chegar ao agente."""
    r = cliente.post("/api/chat", json={"sessao": "s1", "mensagem": "oi"})

    assert r.status_code == 401
    assert "Sessão inválida" in r.json()["detail"]


def test_chat_recusa_sessao_curta(cliente):
    r = cliente.post("/api/chat", json={"sessao": "abc.def", "mensagem": "oi"})
    assert r.status_code == 401


def test_reset_recusa_sessao_forjada(cliente):
    r = cliente.post("/api/reset", json={"sessao": "inventada"})
    assert r.status_code == 401


def test_sessoes_distintas_nao_enxergam_o_historico_um_da_outra(cliente_efetivo):
    """Duas sessões são namespaces distintos no histórico. Um cliente não
    consegue assumir a sessão de outro só porque tem um id válido — o id
    é a credencial, e não é adivinhável."""
    cliente, agente = cliente_efetivo

    s1 = cliente.get("/api/sessao").json()["sessao"]
    s2 = cliente.get("/api/sessao").json()["sessao"]

    cliente.post("/api/chat", json={"sessao": s1, "mensagem": "oi"})
    cliente.post("/api/chat", json={"sessao": s2, "mensagem": "oi"})

    chamadas = [c.args[0] for c in agente.perguntar.call_args_list]
    assert chamadas == [s1, s2]
