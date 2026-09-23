import os

from notion_client import Client

NOTION_VERSION = "2022-06-28"


def get_client() -> Client:
    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise RuntimeError("NOTION_TOKEN não definido no .env")
    return Client(auth=token, notion_version=NOTION_VERSION)


def database_id() -> str:
    value = os.getenv("NOTION_DATABASE_ID")
    if not value:
        raise RuntimeError("NOTION_DATABASE_ID não definido no .env")
    return value


def title_property() -> str:
    return os.getenv("NOTION_TITLE_PROP", "Name")