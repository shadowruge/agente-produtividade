import base64
from email.mime.text import MIMEText

from langchain_core.tools import tool

from config.google_auth import get_service


def _cabecalho(msg: dict, nome: str) -> str:
    for h in msg.get("payload", {}).get("headers", []):
        if h["name"].lower() == nome.lower():
            return str(h["value"])
    return ""


def _texto(payload: dict) -> str:
    """Extrai o primeiro text/plain encontrado, percorrendo as partes recursivamente."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    for parte in payload.get("parts", []) or []:
        texto = _texto(parte)
        if texto:
            return texto
    return ""


@tool
def listar_emails(consulta: str = "is:unread", maximo: int = 10) -> str:
    """Lista e-mails do Gmail. 'consulta' usa a sintaxe de busca do Gmail
    (ex: 'is:unread', 'from:fulano@x.com', 'newer_than:2d'). Retorna id, remetente, assunto e data."""
    svc = get_service("gmail", "v1")
    ids = (
        svc.users()
        .messages()
        .list(userId="me", q=consulta, maxResults=maximo)
        .execute()
        .get("messages", [])
    )
    if not ids:
        return "Nenhum e-mail encontrado."
    linhas = []
    for item in ids:
        m = (
            svc.users()
            .messages()
            .get(
                userId="me",
                id=item["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            )
            .execute()
        )
        linhas.append(
            f"- id={item['id']} | {_cabecalho(m, 'From')} | {_cabecalho(m, 'Subject')} | {_cabecalho(m, 'Date')}"
        )
    return "\n".join(linhas)


@tool
def ler_email(id_email: str) -> str:
    """Lê o conteúdo de um e-mail pelo id (obtido em listar_emails)."""
    m = (
        get_service("gmail", "v1")
        .users()
        .messages()
        .get(userId="me", id=id_email, format="full")
        .execute()
    )
    corpo = _texto(m.get("payload", {})) or m.get("snippet", "")
    return (
        f"De: {_cabecalho(m, 'From')}\nAssunto: {_cabecalho(m, 'Subject')}\n"
        f"Data: {_cabecalho(m, 'Date')}\n\n{corpo[:3000]}"
    )


@tool
def criar_rascunho(para: str, assunto: str, corpo: str) -> str:
    """Cria um RASCUNHO de e-mail no Gmail. Não envia; o usuário revisa e envia manualmente."""
    msg = MIMEText(corpo, "plain", "utf-8")
    msg["to"] = para
    msg["subject"] = assunto
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    get_service("gmail", "v1").users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()
    return f"Rascunho criado para {para} com o assunto '{assunto}'. Ele está na pasta Rascunhos do Gmail."
