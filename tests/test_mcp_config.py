from unittest.mock import AsyncMock, patch

import pytest

from config.mcp_config import load_mcp_tools


async def test_sem_servidores_configurados_retorna_lista_vazia():
    resultado = await load_mcp_tools()
    assert resultado == []


async def test_json_invalido_retorna_lista_vazia_e_nao_levanta(monkeypatch):
    monkeypatch.setenv("MCP_SERVERS", "{isso nao e json valido}")
    from config.settings import reset_settings_cache

    reset_settings_cache()

    resultado = await load_mcp_tools()

    assert resultado == []


async def test_carrega_tools_quando_servidor_configurado(monkeypatch):
    monkeypatch.setenv(
        "MCP_SERVERS",
        '{"clima": {"transport": "streamable_http", "url": "https://exemplo.com/mcp"}}',
    )
    from config.settings import reset_settings_cache

    reset_settings_cache()

    tool_falsa = object()
    cliente_mock = AsyncMock()
    cliente_mock.get_tools.return_value = [tool_falsa]

    with patch(
        "langchain_mcp_adapters.client.MultiServerMCPClient", return_value=cliente_mock
    ) as construtor:
        resultado = await load_mcp_tools()

    construtor.assert_called_once()
    assert resultado == [tool_falsa]


async def test_falha_no_servidor_mcp_nao_derruba_o_agente(monkeypatch):
    monkeypatch.setenv(
        "MCP_SERVERS",
        '{"fora_do_ar": {"transport": "streamable_http", "url": "https://naoexiste.invalid/mcp"}}',
    )
    from config.settings import reset_settings_cache

    reset_settings_cache()

    with patch(
        "langchain_mcp_adapters.client.MultiServerMCPClient",
        side_effect=RuntimeError("conexão recusada"),
    ):
        resultado = await load_mcp_tools()

    assert resultado == []
