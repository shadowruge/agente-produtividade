import os

import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("NOTION_TOKEN")
database_id = os.getenv("NOTION_DATABASE_ID")
title_prop = os.getenv("NOTION_TITLE_PROP")

print("=== CONFIGURAÇÃO ===")
print(f"Database ID: {database_id}")
print(f"Title property: {title_prop}")
print(f"Token carregado: {'SIM' if token else 'NÃO'}")

if not token:
    raise SystemExit("ERRO: NOTION_TOKEN não encontrado.")

if not database_id:
    raise SystemExit("ERRO: NOTION_DATABASE_ID não encontrado.")

url = f"https://api.notion.com/v1/databases/{database_id}"

headers = {
    "Authorization": f"Bearer {token}",
    "Notion-Version": "2022-06-28",
}

print("\n=== TESTE NOTION DATABASE ===")
print(f"GET {url}")

response = requests.get(
    url,
    headers=headers,
    timeout=15,
)

print(f"\nHTTP: {response.status_code}")

try:
    data = response.json()
    print(data)
except Exception:
    print(response.text)