from typing import cast

from langchain_core.tools import tool

from config.notion_config import database_id, get_client, title_property


def _titulo(pagina: dict) -> str:
    for prop in pagina.get("properties", {}).values():
        if prop.get("type") == "title":
            return "".join(t["plain_text"] for t in prop["title"]) or "(sem título)"
    return "(sem título)"


@tool
def buscar_notion(consulta: str) -> str:
    """Busca páginas no Notion pelo título. Só encontra páginas compartilhadas com a integração."""
    resp = cast(
        dict,
        get_client().search(
            query=consulta, filter={"property": "object", "value": "page"}, page_size=10
        ),
    )
    paginas = resp.get("results", [])
    if not paginas:
        return "Nenhuma página encontrada."
    return "\n".join(f"- {_titulo(p)} | {p['url']}" for p in paginas)


@tool
def criar_nota(titulo: str, conteudo: str = "") -> str:
    """Cria uma nova página (nota/tarefa) no banco de dados configurado do Notion."""
    blocos = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": linha[:2000]}}]},
        }
        for linha in conteudo.splitlines()
        if linha.strip()
    ][:100]
    pagina = cast(
        dict,
        get_client().pages.create(
            parent={"database_id": database_id()},
            properties={title_property(): {"title": [{"text": {"content": titulo}}]}},
            children=blocos,
        ),
    )
    return f"Nota criada: {titulo}. Link: {pagina['url']}"
