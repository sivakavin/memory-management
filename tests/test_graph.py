from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent.checkpointer import get_checkpointer
from agent.graph import build_graph
from agent.store import get_store


def make_config(thread_id="thread-1", user_id="user-1"):
    return {"configurable": {"thread_id": thread_id, "user_id": user_id}}


def test_graph_returns_ai_response():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content="Hello! How can I help?"
    )

    with (
        get_store(":memory:") as store,
        patch("agent.graph.get_llm", return_value=mock_llm),
    ):
        graph = build_graph(store=store)

        result = graph.invoke(
            {"messages": [HumanMessage(content="Hi")]},
            config=make_config(),
        )

    assert len(result["messages"]) == 2
    assert result["messages"][-1].content == "Hello! How can I help?"
    mock_llm.invoke.assert_called_once()
    assert mock_llm.invoke.call_args.kwargs["config"]["run_name"] == (
        "chat-response"
    )


def test_graph_compiles_with_sqlite_checkpointer(tmp_path):
    db_path = str(tmp_path / "checkpoints.sqlite")

    with (
        get_checkpointer(db_path) as checkpointer,
        get_store(":memory:") as store,
    ):
        graph = build_graph(checkpointer=checkpointer, store=store)

        assert graph is not None


def test_graph_remembers_messages_with_same_thread_id(tmp_path):
    db_path = str(tmp_path / "checkpoints.sqlite")

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        AIMessage(content="Your name is Ravi."),
        AIMessage(content="Your name is Ravi."),
    ]

    with (
        get_checkpointer(db_path) as checkpointer,
        get_store(":memory:") as store,
        patch("agent.graph.get_llm", return_value=mock_llm),
    ):
        graph = build_graph(checkpointer=checkpointer, store=store)
        config = make_config(thread_id="conversation-1")

        graph.invoke(
            {"messages": [HumanMessage(content="My name is Ravi.")]},
            config=config,
        )

        result = graph.invoke(
            {"messages": [HumanMessage(content="What is my name?")]},
            config=config,
        )

    messages = result["messages"]

    assert len(messages) == 4
    assert messages[0].content == "My name is Ravi."
    assert messages[2].content == "What is my name?"
    assert messages[3].content == "Your name is Ravi."


def test_graph_requires_user_id_in_config():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="ok")

    with (
        get_store(":memory:") as store,
        patch("agent.graph.get_llm", return_value=mock_llm),
    ):
        graph = build_graph(store=store)

        with pytest.raises(KeyError, match="user_id"):
            graph.invoke(
                {"messages": [HumanMessage(content="Hi")]},
                config={"configurable": {"thread_id": "t1"}},
            )


def test_graph_saves_user_message_to_long_term_memory():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="ok")

    with (
        get_store(":memory:") as store,
        patch("agent.graph.get_llm", return_value=mock_llm),
    ):
        graph = build_graph(store=store)

        graph.invoke(
            {"messages": [HumanMessage(content="I love pizza")]},
            config=make_config(user_id="alice"),
        )

        items = store.search(("alice", "memories"))

    assert len(items) == 1
    assert items[0].value["text"] == "I love pizza"
    assert items[0].namespace == ("alice", "memories")


def test_graph_injects_saved_memories_into_system_prompt():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="ok")

    with (
        get_store(":memory:") as store,
        patch("agent.graph.get_llm", return_value=mock_llm),
    ):
        graph = build_graph(store=store)

        graph.invoke(
            {"messages": [HumanMessage(content="My favorite color is blue")]},
            config=make_config(thread_id="t1", user_id="alice"),
        )

        graph.invoke(
            {"messages": [HumanMessage(content="What do you know?")]},
            config=make_config(thread_id="t2", user_id="alice"),
        )

        second_call_messages = mock_llm.invoke.call_args.args[0]

    system_message = second_call_messages[0]

    assert isinstance(system_message, SystemMessage)
    assert "My favorite color is blue" in system_message.content
    assert "when relevant" in system_message.content


def test_graph_isolates_memories_between_users():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="ok")

    with (
        get_store(":memory:") as store,
        patch("agent.graph.get_llm", return_value=mock_llm),
    ):
        graph = build_graph(store=store)

        graph.invoke(
            {"messages": [HumanMessage(content="alice private fact")]},
            config=make_config(thread_id="t1", user_id="alice"),
        )

        mock_llm.invoke.reset_mock()

        graph.invoke(
            {"messages": [HumanMessage(content="hi from bob")]},
            config=make_config(thread_id="t2", user_id="bob"),
        )

        second_call_messages = mock_llm.invoke.call_args.args[0]
        bob_memories = store.search(("bob", "memories"))

    assert "alice private fact" not in second_call_messages[0].content
    assert [item.value["text"] for item in bob_memories] == ["hi from bob"]


def test_graph_forwards_conversation_history_to_llm(tmp_path):
    db_path = str(tmp_path / "checkpoints.sqlite")

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="ok")

    with (
        get_checkpointer(db_path) as checkpointer,
        get_store(":memory:") as store,
        patch("agent.graph.get_llm", return_value=mock_llm),
    ):
        graph = build_graph(checkpointer=checkpointer, store=store)
        config = make_config(thread_id="thread-1")

        graph.invoke(
            {"messages": [HumanMessage(content="first question")]},
            config=config,
        )

        graph.invoke(
            {"messages": [HumanMessage(content="second question")]},
            config=config,
        )

    forwarded = mock_llm.invoke.call_args.args[0]

    contents = [message.content for message in forwarded]

    assert "first question" in contents
    assert "second question" in contents
