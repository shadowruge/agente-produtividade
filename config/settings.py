"""Configuração central do agente.

Todas as variáveis de ambiente usadas pelo projeto passam por aqui.
Isso substitui os `os.getenv(...)` espalhados pelo código por um único
objeto validado (`get_settings()`), o que facilita tanto rodar local
quanto em produção (Render.com), e deixa claro o que precisa ser
configurado no painel do serviço.

Uso:
    from config.settings import get_settings
    settings = get_settings()
    settings.ollama_base_url
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Ambiente / servidor ---
    environment: Literal["development", "production"] = Field(
        default="development",
        description="Usado para ligar proteções extras (ex: exigir AUTH_TOKEN) em produção.",
    )
    host: str = Field(default="127.0.0.1")
    # Render injeta a variável PORT automaticamente; localmente cai no 8000.
    port: int = Field(default=8000)
    # Lista separada por vírgula, ex: "https://meuapp.com,https://outro.com"
    cors_origins: str = Field(default="")

    # --- Autenticação da API web ---
    # Se definido, todo /api/* passa a exigir o header
    # "Authorization: Bearer <API_AUTH_TOKEN>". Em produção isso é
    # obrigatório: sem senha, qualquer pessoa com a URL pública do
    # Render consegue ler e-mails, mexer na agenda e criar notas.
    api_auth_token: str | None = Field(default=None)

    # --- Ollama ---
    ollama_model: str = Field(default="qwen2.5:7b")
    ollama_base_url: str = Field(default="http://localhost:11434")

    # --- Geral ---
    timezone: str = Field(default="America/Sao_Paulo")

    # --- Google ---
    google_credentials_file: str = Field(default="credentials.json")
    google_token_file: str = Field(default="token.json")

    # --- Notion ---
    notion_token: str | None = Field(default=None)
    notion_database_id: str | None = Field(default=None)
    notion_title_prop: str = Field(default="Name")

    # --- MCP (Model Context Protocol) ---
    # JSON com um ou mais servidores MCP externos cujas tools o agente
    # deve carregar além das ferramentas nativas (Google/Gmail/Notion).
    # Formato (mesmo aceito por langchain-mcp-adapters):
    # {
    #   "meu_servidor": {"transport": "streamable_http", "url": "https://.../mcp"},
    #   "outro":        {"transport": "stdio", "command": "python", "args": ["servidor.py"]}
    # }
    mcp_servers: str = Field(default="")

    @field_validator("environment", mode="before")
    @classmethod
    def _lower_env(cls, v: str) -> str:
        return v.lower() if isinstance(v, str) else v

    def google_credentials_path(self) -> Path:
        return ROOT / self.google_credentials_file

    def google_token_path(self) -> Path:
        return ROOT / self.google_token_file

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def mcp_servers_config(self) -> dict:
        """Faz o parse de MCP_SERVERS (JSON). Retorna {} se vazio ou inválido."""
        if not self.mcp_servers.strip():
            return {}
        try:
            data = json.loads(self.mcp_servers)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "MCP_SERVERS não é um JSON válido. Confira a variável de ambiente."
            ) from exc
        if not isinstance(data, dict):
            raise ValueError("MCP_SERVERS deve ser um objeto JSON (dict de servidores).")
        return data

    def is_production(self) -> bool:
        return self.environment == "production"

    def notion_configured(self) -> bool:
        return bool(self.notion_token and self.notion_database_id)


@lru_cache
def get_settings() -> Settings:
    """Instância única (cacheada) das configurações."""
    return Settings()


def reset_settings_cache() -> None:
    """Só para testes: força recarregar as configurações do ambiente."""
    get_settings.cache_clear()
