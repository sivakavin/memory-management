
import hashlib
import logging
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from agent.checkpointer import get_checkpointer
from agent.config import get_settings
from agent.graph import build_graph
from agent.llm import get_llm
from agent.metrics import clear_metrics, init_metrics_db, list_metrics, record_metric
from agent.store import get_store
from agent.tracing import flush_langfuse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Keep database paths in the project root, not the current working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT_DB = PROJECT_ROOT / "checkpoints.sqlite"
MEMORY_DB = PROJECT_ROOT / "long_term_memory.sqlite"
METRICS_DB = PROJECT_ROOT / "request_metrics.sqlite"

# Prevent simultaneous graph invocations in this single-process example.
graph_lock = Lock()

# Long-term memory namespace used to record a user's conversation list.
THREADS_NAMESPACE = "threads"

# Cache LLM connectivity checks (keyed by the credentials used) so polling
# stays cheap without mixing up results between different API keys.
LLM_STATUS_TTL_SECONDS = 20
_llm_status_cache: dict[str, tuple[float, "StatusResponse"]] = {}


def _threads_namespace(user_id: str) -> tuple[str, str]:
    return (user_id, THREADS_NAMESPACE)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _llm_config_from_headers(
    api_key: str | None,
    model: str | None,
    temperature: str | None,
) -> dict[str, Any]:
    """Build the per-request LLM overrides sent by the browser."""
    config: dict[str, Any] = {}

    if api_key and api_key.strip():
        config["api_key"] = api_key.strip()

    if model and model.strip():
        config["model"] = model.strip()

    if temperature is not None and temperature.strip():
        try:
            config["temperature"] = float(temperature)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail="temperature must be a number.",
            ) from exc

    return config


def _key_source(override: dict[str, Any]) -> str:
    """Where the credentials for a request come from: browser or server."""
    if override.get("api_key"):
        return "browser"
    if get_settings().groq_api_key:
        return "server"
    return "none"


def _extract_usage(message: Any) -> tuple[int, int, int]:
    """Return (input, output, total) token counts from an LLM message."""
    usage = getattr(message, "usage_metadata", None) or {}
    if usage:
        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", 0) or 0)
        return input_tokens, output_tokens, total_tokens

    token_usage = (
        getattr(message, "response_metadata", None) or {}
    ).get("token_usage") or {}
    input_tokens = int(token_usage.get("prompt_tokens", 0) or 0)
    output_tokens = int(token_usage.get("completion_tokens", 0) or 0)
    total_tokens = int(
        token_usage.get("total_tokens", input_tokens + output_tokens) or 0
    )
    return input_tokens, output_tokens, total_tokens


def _summarize_title(message: str) -> str:
    title = " ".join(message.strip().split())
    if not title:
        return "New conversation"
    return title if len(title) <= 60 else f"{title[:57]}..."


def _collect_tools_used(messages: list[Any]) -> list[str]:
    """Return tool names used during the latest conversation turn."""
    turn_start = 0
    for index, message in enumerate(messages):
        if getattr(message, "type", "") == "human":
            turn_start = index

    tools: list[str] = []
    for message in messages[turn_start + 1 :]:
        for call in getattr(message, "tool_calls", None) or []:
            if isinstance(call, dict):
                name = call.get("name")
            else:
                name = getattr(call, "name", None)
            if name and str(name) not in tools:
                tools.append(str(name))

        if getattr(message, "type", "") == "tool":
            name = getattr(message, "name", None)
            if name and str(name) not in tools:
                tools.append(str(name))

    return tools


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting memory agent...")

    init_metrics_db(METRICS_DB)

    with (
        get_checkpointer(str(CHECKPOINT_DB)) as checkpointer,
        get_store(str(MEMORY_DB)) as store,
    ):
        app.state.graph = build_graph(
            checkpointer=checkpointer,
            store=store,
        )
        app.state.store = store
        app.state.checkpointer = checkpointer
        logger.info("Memory agent initialized successfully.")

        try:
            yield
        finally:
            flush_langfuse()

    logger.info("Memory agent shut down.")


app = FastAPI(
    title="Memory Management API",
    description="FastAPI interface for the LangGraph memory agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=[
        "Content-Type",
        "X-LLM-Api-Key",
        "X-LLM-Model",
        "X-LLM-Temperature",
    ],
)


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    thread_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=10000)


class ChatResponse(BaseModel):
    user_id: str
    thread_id: str
    answer: str
    model: str
    key_source: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    tools_used: list[str] = Field(default_factory=list)


class MetricItem(BaseModel):
    id: str
    thread_id: str
    model: str
    key_source: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    tools_used: list[str]
    created_at: str


class MetricsResponse(BaseModel):
    user_id: str
    metrics: list[MetricItem]


class ThreadSummary(BaseModel):
    thread_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class ThreadListResponse(BaseModel):
    user_id: str
    threads: list[ThreadSummary]


class ThreadCreateResponse(BaseModel):
    user_id: str
    thread_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class MessageItem(BaseModel):
    role: str
    content: str


class ThreadMessagesResponse(BaseModel):
    user_id: str
    thread_id: str
    messages: list[MessageItem]


class StatusResponse(BaseModel):
    status: str
    llm_connected: bool
    model: str
    detail: str
    server_key_configured: bool
    default_model: str
    key_source: str


def _record_thread(
    user_id: str,
    thread_id: str,
    *,
    first_message: str | None = None,
    message_count: int | None = None,
) -> None:
    """Upsert conversation metadata so it can be listed in the UI."""
    namespace = _threads_namespace(user_id)
    existing = app.state.store.get(namespace, thread_id)
    previous = existing.value if existing else {}

    now = _now_iso()
    title = previous.get("title") or "New conversation"
    if first_message and title == "New conversation":
        title = _summarize_title(first_message)

    app.state.store.put(
        namespace,
        thread_id,
        {
            "thread_id": thread_id,
            "title": title,
            "created_at": previous.get("created_at", now),
            "updated_at": now,
            "message_count": (
                message_count
                if message_count is not None
                else previous.get("message_count", 0)
            ),
        },
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status", response_model=StatusResponse)
def status(
    x_llm_api_key: str | None = Header(default=None, alias="X-LLM-Api-Key"),
    x_llm_model: str | None = Header(default=None, alias="X-LLM-Model"),
    x_llm_temperature: str | None = Header(
        default=None, alias="X-LLM-Temperature"
    ),
):
    """Report whether the LLM is reachable (cached for a short window)."""
    settings = get_settings()
    override = _llm_config_from_headers(
        x_llm_api_key, x_llm_model, x_llm_temperature
    )

    effective_key = override.get("api_key") or settings.groq_api_key
    effective_model = override.get("model") or settings.model

    cache_key = hashlib.sha256(
        f"{effective_key}|{effective_model}|{override.get('temperature')}".encode()
    ).hexdigest()

    now = time.monotonic()
    cached = _llm_status_cache.get(cache_key)
    if cached is not None and now < cached[0]:
        return cached[1]

    server_key_configured = bool(settings.groq_api_key)
    common = {
        "status": "ok",
        "model": effective_model,
        "server_key_configured": server_key_configured,
        "default_model": settings.model,
        "key_source": _key_source(override),
    }

    if not effective_key:
        payload = StatusResponse(
            **common,
            llm_connected=False,
            detail="No API key configured. Add one in LLM settings.",
        )
    else:
        try:
            get_llm(**override).invoke(
                "ping",
                config={
                    "run_name": "llm-connectivity-check",
                    "metadata": {"langfuse_tags": ["health-check"]},
                },
            )
            payload = StatusResponse(
                **common,
                llm_connected=True,
                detail="LLM reachable.",
            )
        except Exception as exc:
            logger.warning("LLM connectivity check failed: %s", exc)
            payload = StatusResponse(
                **common,
                llm_connected=False,
                detail=f"{type(exc).__name__}: {exc}",
            )

    _llm_status_cache[cache_key] = (now + LLM_STATUS_TTL_SECONDS, payload)
    return payload


@app.get("/users/{user_id}/threads", response_model=ThreadListResponse)
def list_threads(user_id: str):
    user_id = user_id.strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id cannot be empty.")

    items = app.state.store.search(
        _threads_namespace(user_id),
        limit=1000,
    )

    threads = [
        ThreadSummary(
            thread_id=item.key,
            title=str(item.value.get("title") or "New conversation"),
            created_at=str(item.value.get("created_at", "")),
            updated_at=str(item.value.get("updated_at", "")),
            message_count=int(item.value.get("message_count", 0) or 0),
        )
        for item in items
    ]
    threads.sort(key=lambda thread: thread.updated_at, reverse=True)

    return ThreadListResponse(user_id=user_id, threads=threads)


@app.post(
    "/users/{user_id}/threads",
    response_model=ThreadCreateResponse,
    status_code=201,
)
def create_thread(user_id: str):
    user_id = user_id.strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id cannot be empty.")

    thread_id = str(uuid.uuid4())
    _record_thread(user_id, thread_id)

    item = app.state.store.get(_threads_namespace(user_id), thread_id)
    value = item.value

    return ThreadCreateResponse(
        user_id=user_id,
        thread_id=thread_id,
        title=str(value.get("title", "New conversation")),
        created_at=str(value.get("created_at", "")),
        updated_at=str(value.get("updated_at", "")),
        message_count=int(value.get("message_count", 0) or 0),
    )


@app.delete("/users/{user_id}/threads/{thread_id}", status_code=204)
def delete_thread(user_id: str, thread_id: str):
    user_id = user_id.strip()
    thread_id = thread_id.strip()
    if not user_id or not thread_id:
        raise HTTPException(
            status_code=422,
            detail="user_id and thread_id cannot be empty.",
        )

    if app.state.store.get(_threads_namespace(user_id), thread_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found for this user.",
        )

    with graph_lock:
        app.state.store.delete(_threads_namespace(user_id), thread_id)
        try:
            app.state.checkpointer.delete_thread(thread_id)
        except Exception as exc:
            logger.warning(
                "Failed to delete checkpoints for thread_id=%s: %s",
                thread_id,
                exc,
            )

    logger.info(
        "Deleted conversation: user_id=%s thread_id=%s", user_id, thread_id
    )


@app.get(
    "/users/{user_id}/threads/{thread_id}/messages",
    response_model=ThreadMessagesResponse,
)
def get_thread_messages(user_id: str, thread_id: str):
    user_id = user_id.strip()
    thread_id = thread_id.strip()
    if not user_id or not thread_id:
        raise HTTPException(
            status_code=422,
            detail="user_id and thread_id cannot be empty.",
        )

    if app.state.store.get(_threads_namespace(user_id), thread_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found for this user.",
        )

    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id,
        }
    }

    state = app.state.graph.get_state(config)
    raw_messages = (state.values or {}).get("messages", []) if state else []

    messages: list[MessageItem] = []
    for message in raw_messages:
        content = getattr(message, "content", "")
        if not isinstance(content, str):
            content = str(content)

        message_type = getattr(message, "type", "")
        if message_type == "human":
            role = "user"
        elif message_type == "ai":
            role = "assistant"
        else:
            role = message_type or "assistant"

        messages.append(MessageItem(role=role, content=content))

    return ThreadMessagesResponse(
        user_id=user_id,
        thread_id=thread_id,
        messages=messages,
    )


@app.get("/users/{user_id}/metrics", response_model=MetricsResponse)
def get_user_metrics(user_id: str):
    user_id = user_id.strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id cannot be empty.")

    rows = list_metrics(METRICS_DB, user_id)
    return MetricsResponse(
        user_id=user_id,
        metrics=[MetricItem(**row) for row in rows],
    )


@app.delete("/users/{user_id}/metrics", status_code=204)
def delete_user_metrics(user_id: str):
    user_id = user_id.strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id cannot be empty.")

    clear_metrics(METRICS_DB, user_id)
    logger.info("Cleared request metrics: user_id=%s", user_id)


@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    x_llm_api_key: str | None = Header(default=None, alias="X-LLM-Api-Key"),
    x_llm_model: str | None = Header(default=None, alias="X-LLM-Model"),
    x_llm_temperature: str | None = Header(
        default=None, alias="X-LLM-Temperature"
    ),
):
    user_id = request.user_id.strip()
    thread_id = request.thread_id.strip()
    message = request.message.strip()

    if not user_id or not thread_id or not message:
        raise HTTPException(
            status_code=422,
            detail="user_id, thread_id, and message cannot be empty.",
        )

    llm_override = _llm_config_from_headers(
        x_llm_api_key, x_llm_model, x_llm_temperature
    )
    settings = get_settings()
    effective_model = llm_override.get("model") or settings.model
    key_source = _key_source(llm_override)

    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id,
            "llm": llm_override,
        }
    }

    logger.info(
        "Chat request received: user_id=%s thread_id=%s model=%s key_source=%s",
        user_id,
        thread_id,
        effective_model,
        key_source,
    )

    try:
        started_at = time.perf_counter()
        with graph_lock:
            result = app.state.graph.invoke(
                {"messages": [HumanMessage(content=message)]},
                config=config,
            )
        latency_ms = round((time.perf_counter() - started_at) * 1000, 1)

        messages = result.get("messages", [])
        if not messages:
            raise RuntimeError(
                "The graph completed but returned no messages."
            )

        last_message = messages[-1]
        answer = getattr(last_message, "content", "")

        # Some models return structured content rather than a plain string.
        if not isinstance(answer, str):
            answer = str(answer)

        if not answer.strip():
            raise RuntimeError(
                "The graph returned an empty assistant response."
            )

        input_tokens, output_tokens, total_tokens = _extract_usage(
            last_message
        )
        tools_used = _collect_tools_used(messages)

        _record_thread(
            user_id,
            thread_id,
            first_message=message,
            message_count=len(messages),
        )

        try:
            record_metric(
                METRICS_DB,
                metric_id=str(uuid.uuid4()),
                user_id=user_id,
                thread_id=thread_id,
                model=effective_model,
                key_source=key_source,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                tools_used=tools_used,
                created_at=_now_iso(),
            )
        except sqlite3.Error as exc:
            logger.warning("Failed to record request metrics: %s", exc)

        logger.info(
            "Chat request completed: latency_ms=%s tokens=%s/%s",
            latency_ms,
            input_tokens,
            output_tokens,
        )

        return ChatResponse(
            user_id=user_id,
            thread_id=thread_id,
            answer=answer,
            model=effective_model,
            key_source=key_source,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            tools_used=tools_used,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("LangGraph invocation failed.")
        raise HTTPException(
            status_code=500,
            detail=f"Agent invocation failed: {type(exc).__name__}: {exc}",
        ) from exc
