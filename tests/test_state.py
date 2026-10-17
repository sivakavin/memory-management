from typing import get_args

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.message import add_messages

from agent.state import AgentState


def test_agent_state_holds_messages():
    state = AgentState(messages=[HumanMessage(content="hi")])

    assert len(state["messages"]) == 1
    assert state["messages"][0].content == "hi"


def test_agent_state_uses_add_messages_reducer():
    annotation = AgentState.__annotations__["messages"]

    assert add_messages in get_args(annotation)


def test_add_messages_reducer_appends_new_messages():
    initial = [HumanMessage(content="hi")]

    updated = add_messages(initial, [AIMessage(content="hello")])

    assert [message.content for message in updated] == ["hi", "hello"]


def test_add_messages_reducer_accepts_single_message():
    initial = [HumanMessage(content="hi")]

    updated = add_messages(initial, AIMessage(content="hello"))

    assert [message.content for message in updated] == ["hi", "hello"]
