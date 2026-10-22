import hashlib

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph

from agent.llm import get_llm
from agent.prompt_loader import load_system_prompt
from agent.state import AgentState
from agent.tracing import get_langfuse_metadata


def _memory_key(text: str) -> str:
    normalized = " ".join(text.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


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
    user_text = str(last_message.content)

    # 2. Save it to long-term memory
    memory_key = _memory_key(user_text)
    store.put(
        namespace,
        memory_key,
        {"text": user_text},
    )

    # store.put(
    # namespace,    user_id,
    # {"text": "I like python,html,css"},
    # ) 

    memories = store.search(namespace, limit=20)

    seen = set()
    memory_lines = []
    for item in memories:
        text = (item.value or {}).get("text")
        if not isinstance(text, str) or item.key == memory_key:
            continue
        normalized = " ".join(text.split())
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        memory_lines.append(normalized[:400])

    memory_text = "\n".join(memory_lines[:10])[:2000]


    llm = get_llm(**_llm_overrides(config))

    system_content = load_system_prompt()
    if memory_text:
        system_content += f"\n\nRelevant long-term memories:\n{memory_text}"

    response = llm.invoke(
        [
            SystemMessage(content=system_content),
            *state["messages"],
        ],
        config={
            "run_name": "chat-response",
            "metadata": get_langfuse_metadata(
                user_id=user_id,
                session_id=config["configurable"].get("thread_id", ""),
            ),
        },
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