import hashlib
import hmac
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agent import tracing


@pytest.fixture(autouse=True)
def clear_langfuse_client_cache():
    tracing.get_langfuse_client.cache_clear()
    yield
    tracing.get_langfuse_client.cache_clear()


def _settings(**overrides):
    values = {
        "langfuse_public_key": "",
        "langfuse_secret_key": "",
        "langfuse_base_url": "",
        "langfuse_capture_content": False,
        "environment": "test",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_tracing_is_disabled_without_credentials(monkeypatch):
    monkeypatch.setattr(tracing, "get_settings", lambda: _settings())

    assert tracing.get_langfuse_client() is None
    assert tracing.get_langfuse_handler() is None
    assert (
        tracing.get_langfuse_metadata(
            user_id="alice",
            session_id="thread",
        )
        == {}
    )


def test_tracing_requires_both_credentials(monkeypatch):
    monkeypatch.setattr(
        tracing,
        "get_settings",
        lambda: _settings(langfuse_public_key="public-key"),
    )

    with pytest.raises(ValueError, match="Configure both"):
        tracing.get_langfuse_client()


def test_langfuse_client_masks_content_by_default(monkeypatch):
    settings = _settings(
        langfuse_public_key="public-key",
        langfuse_secret_key="secret-key",
        langfuse_base_url="https://langfuse.example",
    )
    mock_client = MagicMock()
    langfuse_factory = MagicMock(return_value=mock_client)
    monkeypatch.setattr(tracing, "get_settings", lambda: settings)
    monkeypatch.setattr(tracing, "Langfuse", langfuse_factory)

    tracing.get_langfuse_client()

    kwargs = langfuse_factory.call_args.kwargs
    assert kwargs["base_url"] == "https://langfuse.example"
    assert kwargs["environment"] == "test"
    assert kwargs["mask_otel_spans"] is tracing._mask_otel_spans


def test_content_mask_removes_prompt_and_completion_text():
    identifier = object()
    params = SimpleNamespace(
        spans={
            identifier: SimpleNamespace(
                attributes={
                    "langfuse.observation.input": "private prompt",
                    "langfuse.observation.output": "private answer",
                    "gen_ai.prompt.0.content": "private prompt",
                    "gen_ai.usage.input_tokens": 12,
                    "gen_ai.request.model": "example-model",
                }
            )
        }
    )

    result = tracing._mask_otel_spans(params=params)

    assert set(result.span_patches[identifier].delete_attributes) == {
        "langfuse.observation.input",
        "langfuse.observation.output",
        "gen_ai.prompt.0.content",
    }


def test_trace_metadata_uses_hashed_ids(monkeypatch):
    settings = _settings(
        langfuse_public_key="public-key",
        langfuse_secret_key="secret-key",
    )
    monkeypatch.setattr(tracing, "get_settings", lambda: settings)
    monkeypatch.setattr(tracing, "Langfuse", MagicMock())

    metadata = tracing.get_langfuse_metadata(
        user_id="alice",
        session_id="thread-1",
    )

    expected_user = hmac.new(
        b"secret-key", b"alice", hashlib.sha256
    ).hexdigest()
    expected_session = hmac.new(
        b"secret-key", b"thread-1", hashlib.sha256
    ).hexdigest()
    assert metadata == {
        "langfuse_user_id": expected_user,
        "langfuse_session_id": expected_session,
        "langfuse_tags": ["chat"],
    }
    assert "alice" not in str(metadata)
