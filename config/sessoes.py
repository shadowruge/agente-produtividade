"""Sessões de chat: ids assinados pelo servidor.

Por que isto existe
-------------------
O campo `sessao` da API é enviado pelo navegador. Sem assinatura, qualquer
cliente que adivinhasse — ou copiasse — o id de outra pessoa leria o
histórico dela: as conversas ficam em memória no servidor, indexadas por
esse id. Como o histórico é justamente o que guarda o que o agente
descobriu da agenda e dos e-mails, isso é vazamento de dados, não um
detalhe cosmético.

A solução é tornar o id **inforjável**: o servidor emite
`<nonce>.<assinatura HMAC>` e só aceita ids cuja assinatura confere. O
segredo é o `api_auth_token` quando existe (ou seja, exatamente quem já
passou pela autenticação) e, em desenvolvimento, um segredo aleatório que
nada mais no processo conhece.

Sobre o custo do HMAC
---------------------
Um PBKDF2 aqui seria desperdício: os nonces têm 192 bits de entropia
(`secrets.token_urlsafe(24)`), então adivinhar um nonce válido exige
2^192 tentativas — inviável mesmo com um HMAC-SHA1 simples. E um KDF caro
aqui viraria vetor de negação de serviço: cada validação gastaria dezenas
de milissegundos de CPU, o que um cliente poderia disparar à vontade. O
HMAC direto é a escolha correta, não a frouxa.

O que isto NÃO resolve
----------------------
Isto não é autenticação multiusuário. Com um único `api_auth_token`
compartilhado, todas as pessoas que o conhecem continuam sendo o mesmo
principal e enxergam o mesmo conjunto de sessões. Isolar usuários de
verdade exigiria login com contas, o que muda a natureza do projeto (hoje
é um assistente pessoal, de usuário único). O que se ganha aqui é que o id
deixa de ser adivinhável e um cliente não consegue imitar a sessão de
outro.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading

_SEPARADOR = "."
_cache: dict[str, bytes] = {}
_lock_cache = threading.Lock()
_lock_segredo = threading.Lock()
_segredo_local: bytes | None = None


def _segredo() -> bytes:
    """Segredo de assinatura.

    Se houver token de API configurado, ele é o segredo: quem consegue
    assinar é quem já se autenticou. Sem token (desenvolvimento local), um
    segredo aleatório por processo — as sessões morrem com o reinício,
    assim como o histórico, que também é só em memória.

    O lock é separado do de `_derivado` de propósito: `threading.Lock` não
    é reentrante, e um único lock para os dois levaria a um travamento
    eterno na primeira emissão de sessão.
    """
    global _segredo_local

    from config.settings import get_settings

    token = get_settings().api_auth_token
    if token:
        return hashlib.sha256(f"agente-sessao:{token}".encode()).digest()

    if _segredo_local is None:
        with _lock_segredo:
            if _segredo_local is None:
                _segredo_local = secrets.token_bytes(32)
    return _segredo_local


def _cache_resetado() -> None:
    """Limpa a cache de derivadas. Usado quando o token muda (config salva
    pela tela) e nos testes."""
    with _lock_cache:
        _cache.clear()


def _assinar(nonce: str) -> str:
    segredo = _segredo()
    return hmac.new(segredo, nonce.encode(), hashlib.sha256).hexdigest()[:32]


def emitir() -> str:
    """Cria um id de sessão novo, assinado."""
    nonce = secrets.token_urlsafe(24)
    return f"{nonce}{_SEPARADOR}{_assinar(nonce)}"


def validar(sessao: str | None) -> str | None:
    """Devolve o id se a assinatura confere, senão None.

    A comparação usa compare_digest: a assinatura é uma credencial, e
    comparar com `==` vaza informação por tempo de execução.
    """
    if not sessao or _SEPARADOR not in sessao:
        return None
    nonce, _, assinatura = sessao.partition(_SEPARADOR)
    if not nonce or not assinatura:
        return None
    if not hmac.compare_digest(assinatura, _assinar(nonce)):
        return None
    return sessao
