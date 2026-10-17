from langgraph.graph import END, START, StateGraph
from langchain_core.messages import SystemMessage
from agent.checkpointer import get_checkpointer


from agent.llm import get_llm
from agent.state import AgentState

def call_model(state:AgentState):
    llm = get_llm()

    response = llm.invoke(
        [
            SystemMessage(
                content="You are helpful assistant."
            ),
            *state["messages"]
        ]
    )

    return {"messages":[response]}


def build_graph(checkpointer=None):
    builder = StateGraph(AgentState)

    builder.add_node("chatbot",call_model)
    builder.add_edge(START,"chatbot")
    builder.add_edge("chatbot",END)

    return builder.compile(checkpointer=checkpointer)