from langchain_core.messages import HumanMessage

from agent.checkpointer import get_checkpointer
from agent.graph import build_graph
from agent.store import get_store
from agent.tracing import flush_langfuse


def main():
    print("Converation ID : sample 'user-1'")
    user_id = input("Enter user ID: ").strip()
    thread_id = input("Enter conversation ID: ").strip()

    
    if not user_id or not thread_id:
        print("User ID and conversation ID cannot be empty.")
        return

    config = {"configurable": {
                "thread_id": thread_id,
                "user_id": user_id,}}
    
    namespace = (user_id,"memories")

    try:
        with (
            get_checkpointer("checkpoints.sqlite") as checkpointer,
            get_store("long_term_memory.sqlite") as store,
        ):
            graph = build_graph(
                checkpointer=checkpointer,
                store=store,
            )

            # config = {
            #     "configurable": {
            #         "thread_id": "user-1"
            #     }
            # }

            while True:
                user_input = input("You: ").strip()

                if user_input.lower() in {"exit", "quit"}:
                    break

                if not user_input:
                    continue

                result = graph.invoke(
                    {"messages": [HumanMessage(content=user_input)]},
                    config=config,
                )

                print("Assistant:", result["messages"][-1].content)
    finally:
        flush_langfuse()


if __name__ == "__main__":
    main()