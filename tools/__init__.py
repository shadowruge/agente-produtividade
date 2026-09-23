from tools.google_calendar import criar_evento, listar_eventos
from tools.gmail import criar_rascunho, ler_email, listar_emails
from tools.notion_tools import buscar_notion, criar_nota

ALL_TOOLS = [
    listar_eventos,
    criar_evento,
    listar_emails,
    ler_email,
    criar_rascunho,
    buscar_notion,
    criar_nota,
]
