from notion_client import Client

from config.settings import get_settings

NOTION_VERSION = "2022-06-28"
"""Fixado em 2022-06-28 para o restante do código continuar esperando o
formato de resposta antigo (`properties`, `parent: {database_id}`). O
cliente novo do Notion (>= 3.x) manda a versão mais nova por padrão, o
que mudaria o formato. Sobrevive à migração: o `notion_version` continua
sendo aplicado ao header da requisição."""


def get_client() -> Client:
    token = get_settings().notion_token
    if not token:
        raise RuntimeError("NOTION_TOKEN não definido (tela de configuração ou .env)")
    return Client(auth=token, notion_version=NOTION_VERSION)


def database_id() -> str:
    value = get_settings().notion_database_id
    if not value:
        raise RuntimeError("NOTION_DATABASE_ID não definido (tela de configuração ou .env)")
    return value


def title_property() -> str:
    return get_settings().notion_title_prop
