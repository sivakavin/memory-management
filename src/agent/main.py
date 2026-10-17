from langchain_core.messages import HumanMessage

from agent.checkpointer import get_checkpointer
from agent.graph import build_graph


def main():
    print("Converation ID : sample 'user-1'")
    thread_id = input("Enter conversation ID: ").strip()
    
    if not thread_id:
        print("Conversation ID cannot be empty.")
        return

    config = {"configurable": {"thread_id": thread_id}}

    with get_checkpointer("checkpoints.sqlite") as checkpointer:
        graph = build_graph(checkpointer=checkpointer)

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


if __name__ == "__main__":
    main()