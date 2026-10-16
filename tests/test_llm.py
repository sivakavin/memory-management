
import pytest
from langchain_groq import ChatGroq

from agent.config import get_settings
from agent.llm import get_llm


def test_get_llm_returns_chatgroq(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()

    llm = get_llm()
    settings = get_settings()

    assert isinstance(llm, ChatGroq)
    assert llm.model_name == settings.model
    assert llm.temperature == pytest.approx(
        settings.temperature, abs=1e-7
    )

    get_settings.cache_clear()


def test_get_llm_raises_when_api_key_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    get_settings.cache_clear()

    with pytest.raises(
        ValueError, match="GROQ_API_KEY is missing"
    ):
        get_llm()

    get_settings.cache_clear()
