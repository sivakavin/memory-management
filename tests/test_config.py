from agent.config import Settings

def test_default_settings():
    settings = Settings(_env_file=None)

    assert settings.app_name == "my-agent"
    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert settings.groq_api_key == ""


def test_settings_from_environment(monkeypatch):
    monkeypatch.setenv("APP_NAME", "test-agent")
    monkeypatch.setenv("ENVIRONMENT", "testing")

    settings = Settings(_env_file=None)

    assert settings.app_name == "test-agent"
    assert settings.environment == "testing"
