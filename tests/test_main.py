from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

import agent.main as main_module
from agent.main import main


def _context_manager(value):
    manager = MagicMock()
    manager.__enter__.return_value = value
    manager.__exit__.return_value = False
    return manager


def test_main_returns_when_user_id_is_empty(monkeypatch, capsys):
    inputs = iter(["", "thread-1"])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))

    main()

    out = capsys.readouterr().out
    assert "cannot be empty" in out


def test_main_returns_when_thread_id_is_empty(monkeypatch, capsys):
    inputs = iter(["user-1", ""])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))

    main()

    out = capsys.readouterr().out
    assert "cannot be empty" in out


def test_main_runs_conversation_until_quit(monkeypatch, capsys):
    inputs = iter(["user-1", "thread-1", "hello", "quit"])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "messages": [AIMessage(content="hi there")]
    }

    monkeypatch.setattr(
        main_module, "get_checkpointer", lambda *a, **k: _context_manager("cp")
    )
    monkeypatch.setattr(
        main_module, "get_store", lambda *a, **k: _context_manager("store")
    )
    monkeypatch.setattr(
        main_module, "build_graph", lambda *a, **k: mock_graph
    )
    flush_mock = MagicMock()
    monkeypatch.setattr(main_module, "flush_langfuse", flush_mock)

    main()

    out = capsys.readouterr().out
    assert "hi there" in out
    mock_graph.invoke.assert_called_once()

    _, kwargs = mock_graph.invoke.call_args
    assert kwargs["config"]["configurable"]["user_id"] == "user-1"
    assert kwargs["config"]["configurable"]["thread_id"] == "thread-1"
    flush_mock.assert_called_once()


def test_main_skips_blank_input(monkeypatch):
    inputs = iter(["user-1", "thread-1", "", "quit"])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "messages": [AIMessage(content="ok")]
    }

    monkeypatch.setattr(
        main_module, "get_checkpointer", lambda *a, **k: _context_manager("cp")
    )
    monkeypatch.setattr(
        main_module, "get_store", lambda *a, **k: _context_manager("store")
    )
    monkeypatch.setattr(
        main_module, "build_graph", lambda *a, **k: mock_graph
    )

    main()

    mock_graph.invoke.assert_not_called()
