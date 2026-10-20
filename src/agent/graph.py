import uuid

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph

from agent.llm import get_llm
from agent.state import AgentState


def _llm_overrides(config):
    """Pull optional per-request LLM settings from the runnable config."""
    llm_config = (config or {}).get("configurable", {}).get("llm") or {}
    overrides = {}
    if llm_config.get("api_key"):
        overrides["api_key"] = llm_config["api_key"]
    if llm_config.get("model"):
        overrides["model"] = llm_config["model"]
    if llm_config.get("temperature") is not None:
        overrides["temperature"] = llm_config["temperature"]
    return overrides


def call_model(state:AgentState,config,*,store):
    user_id=config["configurable"]["user_id"]
    namespace= (user_id,"memories")


    # 1. Get the latest user message
    last_message = state["messages"][-1]
    user_text = last_message.content

    # 2. Save it to long-term memory
    store.put(
        namespace,
        str(uuid.uuid4()),
        {"text": user_text},
    )

    # store.put(
    # namespace,    user_id,
    # {"text": "I like python,html,css"},
    # ) 

    memories = store.search(namespace,query="user facts")
    
    memory_text = "\n".join(
        item.value.get("text"," ") for item in memories
    ) 


    llm = get_llm(**_llm_overrides(config))

    response = llm.invoke(
        [
             SystemMessage(
                content=(
                    "You are a helpful assistant. Use these saved memories "
                    f"when relevant:\n{memory_text}"
                )
            ),
            *state["messages"],
        ]
    )

    return {"messages":[response]}


def build_graph(checkpointer=None,store=None):
    builder = StateGraph(AgentState)

    builder.add_node("chatbot",call_model)
    builder.add_edge(START,"chatbot")
    builder.add_edge("chatbot",END)

    return builder.compile(
        checkpointer=checkpointer,
        store=store
        )