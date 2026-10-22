from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import agent.api as api_module
from agent.api import app


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content="Hello from the agent")
    return llm


@pytest.fixture
def graph_llm(monkeypatch, mock_llm):
    spy = MagicMock(return_value=mock_llm)
    monkeypatch.setattr("agent.graph.get_llm", spy)
    return spy


@pytest.fixture
def status_llm(monkeypatch, mock_llm):
    spy = MagicMock(return_value=mock_llm)
    monkeypatch.setattr(api_module, "get_llm", spy)
    return spy


@pytest.fixture
def client(tmp_path, monkeypatch, graph_llm, status_llm):
    monkeypatch.setattr(api_module, "CHECKPOINT_DB", tmp_path / "checkpoints.sqlite")
    monkeypatch.setattr(api_module, "MEMORY_DB", tmp_path / "long_term_memory.sqlite")
    monkeypatch.setattr(api_module, "METRICS_DB", tmp_path / "request_metrics.sqlite")

    settings = MagicMock()
    settings.groq_api_key = "server-key"
    settings.model = "server-model"
    monkeypatch.setattr(api_module, "get_settings", lambda: settings)

    api_module._llm_status_cache.clear()

    with TestClient(app) as test_client:
        yield test_client


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_reports_llm_connected(client):
    response = client.get("/status")

    assert response.status_code == 200
    body = response.json()
    assert body["llm_connected"] is True
    assert body["model"] == "server-model"
    assert body["default_model"] == "server-model"
    assert body["server_key_configured"] is True
    assert body["key_source"] == "server"


def test_status_reports_disconnected_when_llm_fails(client, monkeypatch):
    api_module._llm_status_cache.clear()

    def boom(**kwargs):
        raise RuntimeError("no connection")

    monkeypatch.setattr(api_module, "get_llm", boom)

    response = client.get("/status")

    assert response.status_code == 200
    body = response.json()
    assert body["llm_connected"] is False
    assert "no connection" in body["detail"]


def test_status_uses_custom_key_from_header(client, status_llm):
    response = client.get(
        "/status",
        headers={"X-LLM-Api-Key": "ui-key", "X-LLM-Model": "ui-model"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "ui-model"
    assert body["llm_connected"] is True
    assert body["key_source"] == "browser"
    assert status_llm.call_args.kwargs["api_key"] == "ui-key"
    assert status_llm.call_args.kwargs["model"] == "ui-model"


def test_status_disconnected_when_no_key_anywhere(client, monkeypatch):
    monkeypatch.setattr(
        api_module, "get_settings", lambda: _settings("")
    )
    api_module._llm_status_cache.clear()

    response = client.get("/status")

    body = response.json()
    assert body["llm_connected"] is False
    assert body["server_key_configured"] is False
    assert body["key_source"] == "none"
    assert "No API key" in body["detail"]


def _settings(groq_api_key):
    settings = MagicMock()
    settings.groq_api_key = groq_api_key
    settings.model = "server-model"
    return settings


def test_list_threads_is_empty_for_new_user(client):
    response = client.get("/users/alice/threads")

    assert response.status_code == 200
    assert response.json() == {"user_id": "alice", "threads": []}


def test_create_thread_returns_and_lists_thread(client):
    created = client.post("/users/alice/threads")

    assert created.status_code == 201
    thread_id = created.json()["thread_id"]

    listed = client.get("/users/alice/threads").json()["threads"]

    assert [thread["thread_id"] for thread in listed] == [thread_id]
    assert listed[0]["title"] == "New conversation"


def test_chat_records_thread_and_returns_answer(client):
    response = client.post(
        "/chat",
        json={
            "user_id": "alice",
            "thread_id": "thread-1",
            "message": "My name is Ravi",
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "Hello from the agent"
    assert response.json()["key_source"] == "server"
    assert response.json()["model"] == "server-model"
    assert response.json()["latency_ms"] >= 0
    assert response.json()["input_tokens"] == 0
    assert response.json()["output_tokens"] == 0
    assert response.json()["total_tokens"] == 0
    assert response.json()["tools_used"] == []

    threads = client.get("/users/alice/threads").json()["threads"]
    assert len(threads) == 1
    assert threads[0]["thread_id"] == "thread-1"
    assert threads[0]["title"] == "My name is Ravi"
    assert threads[0]["message_count"] == 2


def test_chat_forwards_custom_llm_headers(client, graph_llm):
    response = client.post(
        "/chat",
        json={"user_id": "alice", "thread_id": "t1", "message": "hi"},
        headers={
            "X-LLM-Api-Key": "ui-key",
            "X-LLM-Model": "ui-model",
            "X-LLM-Temperature": "0.5",
        },
    )

    assert response.status_code == 200
    kwargs = graph_llm.call_args.kwargs
    assert kwargs["api_key"] == "ui-key"
    assert kwargs["model"] == "ui-model"
    assert kwargs["temperature"] == 0.5
    assert response.json()["key_source"] == "browser"
    assert response.json()["model"] == "ui-model"


def test_chat_without_headers_uses_server_defaults(client, graph_llm):
    client.post(
        "/chat",
        json={"user_id": "alice", "thread_id": "t1", "message": "hi"},
    )

    assert graph_llm.call_args.kwargs == {}


def test_chat_reports_token_usage(client, mock_llm):
    mock_llm.invoke.return_value = AIMessage(
        content="hi",
        usage_metadata={
            "input_tokens": 11,
            "output_tokens": 7,
            "total_tokens": 18,
        },
    )

    response = client.post(
        "/chat",
        json={"user_id": "alice", "thread_id": "t1", "message": "hello"},
    )

    body = response.json()
    assert body["input_tokens"] == 11
    assert body["output_tokens"] == 7
    assert body["total_tokens"] == 18


def test_get_thread_messages_returns_history(client):
    client.post(
        "/chat",
        json={"user_id": "alice", "thread_id": "thread-1", "message": "hi"},
    )

    response = client.get("/users/alice/threads/thread-1/messages")

    assert response.status_code == 200
    messages = response.json()["messages"]
    assert messages[0] == {"role": "user", "content": "hi"}
    assert messages[1] == {"role": "assistant", "content": "Hello from the agent"}


def test_get_messages_for_unknown_thread_returns_404(client):
    response = client.get("/users/alice/threads/missing/messages")

    assert response.status_code == 404


def test_delete_thread_removes_it_from_list(client):
    client.post(
        "/chat",
        json={"user_id": "alice", "thread_id": "thread-1", "message": "hi"},
    )

    deleted = client.delete("/users/alice/threads/thread-1")

    assert deleted.status_code == 204
    assert client.get("/users/alice/threads").json()["threads"] == []
    assert client.get("/users/alice/threads/thread-1/messages").status_code == 404


def test_delete_unknown_thread_returns_404(client):
    response = client.delete("/users/alice/threads/missing")

    assert response.status_code == 404


def test_delete_thread_is_isolated_between_users(client):
    client.post(
        "/chat",
        json={"user_id": "alice", "thread_id": "thread-1", "message": "hi"},
    )

    assert client.delete("/users/bob/threads/thread-1").status_code == 404
    assert client.delete("/users/alice/threads/thread-1").status_code == 204


def test_threads_are_isolated_between_users(client):
    client.post(
        "/chat",
        json={"user_id": "alice", "thread_id": "thread-1", "message": "hi"},
    )

    assert client.get("/users/bob/threads").json()["threads"] == []
    assert client.get("/users/bob/threads/thread-1/messages").status_code == 404


def test_chat_rejects_empty_message(client):
    response = client.post(
        "/chat",
        json={"user_id": "alice", "thread_id": "t1", "message": "   "},
    )

    assert response.status_code == 422


def test_chat_rejects_non_numeric_temperature(client):
    response = client.post(
        "/chat",
        json={"user_id": "alice", "thread_id": "t1", "message": "hi"},
        headers={"X-LLM-Temperature": "hot"},
    )

    assert response.status_code == 422


def test_chat_records_metrics(client, mock_llm):
    mock_llm.invoke.return_value = AIMessage(
        content="hi",
        usage_metadata={
            "input_tokens": 11,
            "output_tokens": 7,
            "total_tokens": 18,
        },
    )

    client.post(
        "/chat",
        json={"user_id": "alice", "thread_id": "t1", "message": "hello"},
    )

    response = client.get("/users/alice/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "alice"
    assert len(body["metrics"]) == 1
    metric = body["metrics"][0]
    assert metric["thread_id"] == "t1"
    assert metric["input_tokens"] == 11
    assert metric["output_tokens"] == 7
    assert metric["total_tokens"] == 18
    assert metric["tools_used"] == []
    assert metric["created_at"]


def test_metrics_are_isolated_between_users(client):
    client.post(
        "/chat",
        json={"user_id": "alice", "thread_id": "t1", "message": "hello"},
    )

    assert client.get("/users/bob/metrics").json()["metrics"] == []


def test_clear_metrics_removes_user_history(client):
    client.post(
        "/chat",
        json={"user_id": "alice", "thread_id": "t1", "message": "hello"},
    )

    response = client.delete("/users/alice/metrics")

    assert response.status_code == 204
    assert client.get("/users/alice/metrics").json()["metrics"] == []


def test_collect_tools_used_only_for_latest_turn():
    messages = [
        HumanMessage(content="old question"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "old_tool",
                    "args": {},
                    "id": "old-1",
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(content="old result", tool_call_id="old-1", name="old_tool"),
        HumanMessage(content="new question"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search",
                    "args": {},
                    "id": "new-1",
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(content="new result", tool_call_id="new-1", name="search"),
        AIMessage(content="done"),
    ]

    assert api_module._collect_tools_used(messages) == ["search"]
