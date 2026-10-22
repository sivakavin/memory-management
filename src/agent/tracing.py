import hashlib
import hmac
from functools import lru_cache
from typing import Any

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from langfuse.types import (
    MaskOtelSpansParams,
    MaskOtelSpansResult,
    OtelSpanPatch,
)

from agent.config import get_settings

_CONTENT_ATTRIBUTES = {
    "langfuse.observation.input",
    "langfuse.observation.output",
    "langfuse.trace.input",
    "langfuse.trace.output",
}


def _is_content_attribute(name: str) -> bool:
    return name in _CONTENT_ATTRIBUTES or (
        name.startswith(("gen_ai.prompt.", "gen_ai.completion."))
        and name.endswith(".content")
    )


def _mask_otel_spans(
    *, params: MaskOtelSpansParams
) -> MaskOtelSpansResult | None:
    patches = {}
    for identifier, span in params.spans.items():
        content_attributes = [
            name
            for name in span.attributes
            if _is_content_attribute(name)
        ]
        if content_attributes:
            patches[identifier] = OtelSpanPatch(
                delete_attributes=content_attributes
            )

    return MaskOtelSpansResult(span_patches=patches) if patches else None


@lru_cache
def get_langfuse_client() -> Langfuse | None:
    settings = get_settings()
    public_key = settings.langfuse_public_key.strip()
    secret_key = settings.langfuse_secret_key.strip()

    if not public_key and not secret_key:
        return None
    if not public_key or not secret_key:
        raise ValueError(
            "Configure both LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY "
            "to enable Langfuse tracing."
        )

    return Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        base_url=settings.langfuse_base_url.strip() or None,
        environment=settings.environment,
        mask_otel_spans=(
            None if settings.langfuse_capture_content else _mask_otel_spans
        ),
    )


def get_langfuse_handler() -> CallbackHandler | None:
    settings = get_settings()
    if get_langfuse_client() is None:
        return None
    return CallbackHandler(public_key=settings.langfuse_public_key.strip())


def get_langfuse_metadata(
    *, user_id: str, session_id: str
) -> dict[str, Any]:
    settings = get_settings()
    if get_langfuse_client() is None:
        return {}

    secret = settings.langfuse_secret_key.encode("utf-8")
    user_hash = hmac.new(
        secret, user_id.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    session_hash = hmac.new(
        secret, session_id.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return {
        "langfuse_user_id": user_hash,
        "langfuse_session_id": session_hash,
        "langfuse_tags": ["chat"],
    }


def flush_langfuse() -> None:
    if get_langfuse_client.cache_info().currsize:
        client = get_langfuse_client()
        if client is not None:
            client.flush()
