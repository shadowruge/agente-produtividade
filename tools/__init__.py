from langchain_core.tools import BaseTool

from tools.google_calendar import criar_evento, listar_eventos
from tools.gmail import criar_rascunho, ler_email, listar_emails
from tools.notion_tools import buscar_notion, criar_nota

# Ferramentas nativas do projeto (sempre disponíveis, sem dependência de rede
# externa além das próprias APIs Google/Notion).
BASE_TOOLS: list[BaseTool] = [
    listar_eventos,
    criar_evento,
    listar_emails,
    ler_email,
    criar_rascunho,
    buscar_notion,
    criar_nota,
]

# Mantido por compatibilidade com código existente (ex: modo --cli) que
# importa ALL_TOOLS diretamente e não precisa das ferramentas MCP.
ALL_TOOLS: list[BaseTool] = BASE_TOOLS


async def get_all_tools() -> list[BaseTool]:
    """BASE_TOOLS + ferramentas de servidores MCP configurados (se houver).

    Use esta função (em vez de ALL_TOOLS) sempre que houver um event loop
    disponível — é o caso da interface web, que carrega as ferramentas MCP
    uma vez, na inicialização do servidor.
    """
    from config.mcp_config import load_mcp_tools

    mcp_tools = await load_mcp_tools()
    return [*BASE_TOOLS, *mcp_tools]
