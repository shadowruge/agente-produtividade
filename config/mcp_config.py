"""Carregamento de ferramentas (tools) de servidores MCP externos.

O agente já usa ferramentas "nativas" (Google Calendar, Gmail, Notion,
em tools/). Este módulo permite, opcionalmente, plugar ferramentas de
servidores MCP (Model Context Protocol) de terceiros — por exemplo um
servidor MCP de outra equipe, um serviço SaaS que exponha MCP, etc.

Configuração via variável de ambiente MCP_SERVERS (JSON), ver
config/settings.py para o formato. Se a variável estiver vazia, ou se
a dependência opcional `langchain-mcp-adapters` não estiver instalada,
a função simplesmente retorna uma lista vazia — o agente continua
funcionando normalmente só com as ferramentas nativas.
"""

from __future__ import annotations

import logging

from langchain_core.tools import BaseTool

from config.settings import get_settings

logger = logging.getLogger(__name__)


async def load_mcp_tools() -> list[BaseTool]:
    """Retorna as tools dos servidores MCP configurados em MCP_SERVERS.

    Nunca levanta exceção por falha de rede/servidor MCP individual —
    um servidor fora do ar não deve derrubar o agente inteiro. Em caso
    de erro, registra um aviso no log e segue sem aquelas ferramentas.
    """
    settings = get_settings()

    try:
        servers = settings.mcp_servers_config()
    except ValueError as exc:
        logger.warning("Configuração MCP_SERVERS inválida, ignorando: %s", exc)
        return []

    if not servers:
        return []

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        logger.warning(
            "MCP_SERVERS configurado, mas o pacote 'langchain-mcp-adapters' não "
            "está instalado. Adicione-o ao requirements.txt para usar servidores "
            "MCP externos."
        )
        return []

    try:
        client = MultiServerMCPClient(servers)
        tools = await client.get_tools()
    except Exception:  # noqa: BLE001 - qualquer falha aqui não deve derrubar o agente
        logger.exception("Falha ao carregar ferramentas dos servidores MCP configurados.")
        return []

    logger.info("Carregadas %d ferramenta(s) de %d servidor(es) MCP.", len(tools), len(servers))
    return tools
