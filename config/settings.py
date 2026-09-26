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

Prioridade dos valores (da mais forte para a mais fraca):

    1. argumentos de `Settings(...)`   (usado nos testes)
    2. variáveis de ambiente reais      (é assim que o Render injeta as chaves)
    3. arquivo de configuração local    (`.config.local.json`, escrito pela tela)
    4. arquivo `.env`                   (mantido por compatibilidade)
    5. padrões do código

Ou seja: a tela de configuração web preenche o que o `.env` não define, mas
nunca sobrescreve uma variável de ambiente real — que é exatamente o que
protege a configuração de produção.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from config import secrets_store

ROOT = Path(__file__).resolve().parent.parent


class _ArquivoConfigSource(PydanticBaseSettingsSource):
    """Fonte de configuração que lê o arquivo escrito pela tela web
    (`.config.local.json`). Fica abaixo das variáveis de ambiente e acima
    do `.env`.

    Um campo só é aplicado se a variável de ambiente correspondente estiver
    ausente ou *vazia*. Tratar o vazio como "não definido" é o que evita a
    mesma armadilha do `API_AUTH_TOKEN=`: um `.env` gerado do exemplo
    deixaria todos os campos com `NOME=` e esconderia o que foi salvo na
    tela, sem nenhum aviso.
    """

    # `field` é exigido pela assinatura da classe-base; a fonte decide o
    # valor pelo nome, então não precisa inspecionar o FieldInfo.
    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:  # noqa: ARG002
        return secrets_store.ler().get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        dados = secrets_store.ler()
        return {
            nome: valor
            for nome, valor in dados.items()
            if nome in self.settings_cls.model_fields
            and str(valor).strip()
            and not os.getenv(nome.upper(), "").strip()
        }


class _EnvSemVazios(PydanticBaseSettingsSource):
    """Filtra as variáveis de ambiente, descartando as vazias.

    Sem isso, `ENABLED_TOOLS=` (como viria de um `.env` gerado do exemplo)
    contaria como "definido" e esconderia o valor salvo na tela — a mesma
    armadilha do `API_AUTH_TOKEN=`. Campo em branco significa "não defini",
    que é a intenção de quem deixa em branco.

    A fonte do arquivo (`_ArquivoConfigSource`) faz o mesmo pela metade, mas
    não basta: a mesclagem do pydantic-settings dá a primeira fonte que
    responder o campo, então a variável vazia já venceria antes de a fonte do
    arquivo ser consultada.
    """

    def __init__(self, settings_cls: Any, env_settings: Any) -> None:
        super().__init__(settings_cls)
        self._env: Any = env_settings

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return cast("tuple[Any, str, bool]", self._env.get_field_value(field, field_name))

    def __call__(self) -> dict[str, Any]:
        return {
            chave: valor
            for chave, valor in self._env().items()
            if not (isinstance(valor, str) and not valor.strip())
        }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Ancorado na raiz do projeto (e não no diretório atual) para que o
        # servidor encontre o .env de onde for chamado.
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Any,
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, ...]:
        return (
            init_settings,
            _EnvSemVazios(settings_cls, env_settings),
            _ArquivoConfigSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )

    # --- Ambiente / servidor ---
    environment: Literal["development", "production"] = Field(
        default="development",
        description="Usado para ligar proteções extras (ex: exigir API_AUTH_TOKEN) em produção.",
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

    # --- Ferramentas e skills (tela de configuração) ---
    # CSV com os nomes das ferramentas habilitadas. Vazio = todas ligadas,
    # que preserva o comportamento original. Ver `tools/__init__.py`.
    enabled_tools: str = Field(default="")
    # Skills: instruções extras injetadas no system prompt.
    # JSON no formato [{"nome": "...", "instrucoes": "..."}]. Vazio = nenhuma.
    skills: str = Field(default="")

    # --- MCP (Model Context Protocol) ---
    # JSON com um ou mais servidores MCP externos cujas tools o agente
    # deve carregar além das ferramentas nativas (Google/Gmail/Notion).
    # Formato (mesmo aceito por langchain-mcp-adapters):
    # {
    #   "meu_servidor": {"transport": "streamable_http", "url": "https://.../mcp"},
    #   "outro":        {"transport": "stdio", "command": "python", "args": ["servidor.py"]}
    # }
    mcp_servers: str = Field(default="")

    # --- Onde a tela de configuração grava os valores ---
    # Escrito por config/secrets_store.py; lido direto do ambiente lá para
    # evitar ciclo de importação. Aqui é só para exibir na tela.
    config_file: str = Field(default=secrets_store.ARQUIVO_PADRAO)

    # ------------------------------------------------------------------
    # Validadores
    # ------------------------------------------------------------------
    # Um `.env` ou um campo vazio na tela produz string vazia, não None.
    # Sem esta normalização, `API_AUTH_TOKEN=` (exatamente como vem no
    # `.env.example`) era lido como token configurado e derrubava TODAS as
    # requisições com 401, porque a guarda checava `token is None`.
    @field_validator("api_auth_token", "notion_token", "notion_database_id", mode="before")
    @classmethod
    def _vazio_vira_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("cors_origins", "enabled_tools", "mcp_servers", "skills", mode="before")
    @classmethod
    def _normaliza_texto(cls, v: Any) -> Any:
        return v.strip() if isinstance(v, str) else v

    @field_validator("environment", mode="before")
    @classmethod
    def _lower_env(cls, v: Any) -> Any:
        return v.lower() if isinstance(v, str) else v

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def google_credentials_path(self) -> Path:
        return ROOT / self.google_credentials_file

    def google_token_path(self) -> Path:
        return ROOT / self.google_token_file

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def enabled_tool_list(self) -> list[str]:
        """Ferramentas habilitadas. Vazio significa 'todas'."""
        return [t.strip() for t in self.enabled_tools.split(",") if t.strip()]

    def skills_list(self) -> list[dict[str, str]]:
        """Skills configuradas. JSON malformado é ignorado (não derruba o
        servidor) — mesmo tratamento dado a MCP_SERVERS."""
        if not self.skills.strip():
            return []
        try:
            dados = json.loads(self.skills)
        except json.JSONDecodeError:
            return []
        if not isinstance(dados, list):
            return []
        return [
            {"nome": str(s.get("nome", "")), "instrucoes": str(s.get("instrucoes", ""))}
            for s in dados
            if isinstance(s, dict)
        ]

    def skills_texto(self) -> str:
        """Skills formatadas para dentro do system prompt."""
        partes = []
        for skill in self.skills_list():
            nome = skill["nome"].strip() or "regra"
            instrucoes = skill["instrucoes"].strip()
            if instrucoes:
                partes.append(f"[{nome}] {instrucoes}")
        return "\n".join(partes)

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
            # ValueError, e não TypeError: quem chama é
            # `load_mcp_tools`, que trata configuração inválida como
            # " MCP desligado", não como erro de programação.
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
    """Invalida o cache. Use após gravar configuração pela tela web (para a
    mudança valer sem reiniciar o servidor) e nos testes."""
    get_settings.cache_clear()
