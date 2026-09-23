import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

from config.google_auth import get_service


def _tz() -> ZoneInfo:
    return ZoneInfo(os.getenv("TIMEZONE", "America/Sao_Paulo"))


@tool
def listar_eventos(dias: int = 7) -> str:
    """Lista os eventos da agenda do Google Calendar dos próximos N dias (padrão 7)."""
    agora = datetime.now(_tz())
    resp = (
        get_service("calendar", "v3")
        .events()
        .list(
            calendarId="primary",
            timeMin=agora.isoformat(),
            timeMax=(agora + timedelta(days=dias)).isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=25,
        )
        .execute()
    )
    eventos = resp.get("items", [])
    if not eventos:
        return f"Nenhum evento nos próximos {dias} dias."
    linhas = []
    for e in eventos:
        inicio = e["start"].get("dateTime", e["start"].get("date"))
        linhas.append(f"- {inicio} | {e.get('summary', '(sem título)')}")
    return "\n".join(linhas)


@tool
def criar_evento(titulo: str, inicio: str, fim: str, descricao: str = "") -> str:
    """Cria um evento no Google Calendar.
    inicio e fim devem estar em ISO 8601 sem fuso, ex: 2026-09-22T14:00:00."""
    tz = os.getenv("TIMEZONE", "America/Sao_Paulo")
    corpo = {
        "summary": titulo,
        "description": descricao,
        "start": {"dateTime": inicio, "timeZone": tz},
        "end": {"dateTime": fim, "timeZone": tz},
    }
    criado = get_service("calendar", "v3").events().insert(calendarId="primary", body=corpo).execute()
    return f"Evento criado: {criado.get('summary')} ({inicio} → {fim}). Link: {criado.get('htmlLink')}"
