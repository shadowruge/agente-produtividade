import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parent.parent

# Se mudar os escopos, apague o token.json para autorizar de novo.
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",  # criar rascunhos (não envia)
]


def _credentials_file() -> Path:
    return ROOT / os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")


def token_file() -> Path:
    return ROOT / os.getenv("GOOGLE_TOKEN_FILE", "token.json")


def get_credentials() -> Credentials:
    creds = None
    if token_file().exists():
        creds = Credentials.from_authorized_user_file(str(token_file()), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not _credentials_file().exists():
                raise FileNotFoundError(
                    f"Arquivo {_credentials_file().name} não encontrado. "
                    "Baixe o OAuth client (Desktop app) no Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(_credentials_file()), SCOPES)
            creds = flow.run_local_server(port=0)
        token_file().write_text(creds.to_json())
    return creds


def get_service(api: str, version: str):
    return build(api, version, credentials=get_credentials(), cache_discovery=False)
