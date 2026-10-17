from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage
from agent.graph import build_graph
from agent.checkpointer import get_checkpointer



def test_graph_returns_ai_response():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content="Hello! How can I help?"
    )

    with patch("agent.graph.get_llm", return_value=mock_llm):
        graph = build_graph()

        result = graph.invoke(
            {"messages": [HumanMessage(content="Hi")]}
        )

    assert len(result["messages"]) == 2
    assert result["messages"][-1].content == "Hello! How can I help?"
    mock_llm.invoke.assert_called_once()


def test_graph_compiles_with_sqlite_checkpointer(tmp_path):
    db_path = str(tmp_path / "checkpoints.sqlite")

    with get_checkpointer(db_path) as checkpointer:
        graph = build_graph(checkpointer=checkpointer)

        assert graph is not None