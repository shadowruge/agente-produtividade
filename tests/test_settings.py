import pytest

from config.settings import get_settings, reset_settings_cache


def test_defaults(settings):
    assert settings.environment == "development"
    assert settings.ollama_model == "qwen2.5:7b"
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.timezone == "America/Sao_Paulo"
    assert settings.is_production() is False
    assert settings.notion_configured() is False


def test_env_override(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:latest")
    monkeypatch.setenv("PORT", "9000")
    reset_settings_cache()

    settings = get_settings()

    assert settings.environment == "production"
    assert settings.is_production() is True
    assert settings.ollama_model == "llama3.2:latest"
    assert settings.port == 9000


def test_cors_origin_list_parses_csv(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.com, https://b.com")
    reset_settings_cache()

    settings = get_settings()

    assert settings.cors_origin_list() == ["https://a.com", "https://b.com"]


def test_cors_origin_list_empty_by_default(settings):
    assert settings.cors_origin_list() == []


def test_notion_configured_true_when_both_set(monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "abc")
    monkeypatch.setenv("NOTION_DATABASE_ID", "123")
    reset_settings_cache()

    settings = get_settings()

    assert settings.notion_configured() is True


def test_mcp_servers_config_empty_by_default(settings):
    assert settings.mcp_servers_config() == {}


def test_mcp_servers_config_parses_json(monkeypatch):
    monkeypatch.setenv(
        "MCP_SERVERS",
        '{"clima": {"transport": "streamable_http", "url": "https://exemplo.com/mcp"}}',
    )
    reset_settings_cache()

    settings = get_settings()

    assert settings.mcp_servers_config() == {
        "clima": {"transport": "streamable_http", "url": "https://exemplo.com/mcp"}
    }


def test_mcp_servers_config_invalid_json_raises(monkeypatch):
    monkeypatch.setenv("MCP_SERVERS", "{isso nao e json}")
    reset_settings_cache()

    settings = get_settings()

    with pytest.raises(ValueError):
        settings.mcp_servers_config()


def test_mcp_servers_config_rejects_non_dict(monkeypatch):
    monkeypatch.setenv("MCP_SERVERS", "[1, 2, 3]")
    reset_settings_cache()

    settings = get_settings()

    with pytest.raises(ValueError):
        settings.mcp_servers_config()


def test_google_paths_are_relative_to_project_root(settings):
    assert settings.google_credentials_path().name == "credentials.json"
    assert settings.google_token_path().name == "token.json"
