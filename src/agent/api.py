
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage

from agent.checkpointer import get_checkpointer
from agent.store import get_store
from agent.graph import build_graph


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Keep database paths in the project root, not the current working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT_DB = PROJECT_ROOT / "checkpoints.sqlite"
MEMORY_DB = PROJECT_ROOT / "long_term_memory.sqlite"

# Prevent simultaneous graph invocations in this single-process example.
graph_lock = Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting memory agent...")

    with (
        get_checkpointer(str(CHECKPOINT_DB)) as checkpointer,
        get_store(str(MEMORY_DB)) as store,
    ):
        app.state.graph = build_graph(
            checkpointer=checkpointer,
            store=store,
        )
        logger.info("Memory agent initialized successfully.")

        yield

    logger.info("Memory agent shut down.")


app = FastAPI(
    title="Memory Management API",
    description="FastAPI interface for the LangGraph memory agent",
    version="1.0.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    thread_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=10000)


class ChatResponse(BaseModel):
    user_id: str
    thread_id: str
    answer: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    user_id = request.user_id.strip()
    thread_id = request.thread_id.strip()
    message = request.message.strip()

    if not user_id or not thread_id or not message:
        raise HTTPException(
            status_code=422,
            detail="user_id, thread_id, and message cannot be empty.",
        )

    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id,
        }
    }

    logger.info(
        "Chat request received: user_id=%s thread_id=%s",
        user_id,
        thread_id,
    )

    try:
        with graph_lock:
            result = app.state.graph.invoke(
                {"messages": [HumanMessage(content=message)]},
                config=config,
            )

        messages = result.get("messages", [])
        if not messages:
            raise RuntimeError(
                "The graph completed but returned no messages."
            )

        last_message = messages[-1]
        answer = getattr(last_message, "content", "")

        # Some models return structured content rather than a plain string.
        if not isinstance(answer, str):
            answer = str(answer)

        if not answer.strip():
            raise RuntimeError(
                "The graph returned an empty assistant response."
            )

        logger.info("Chat request completed successfully.")

        return ChatResponse(
            user_id=user_id,
            thread_id=thread_id,
            answer=answer,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("LangGraph invocation failed.")
        raise HTTPException(
            status_code=500,
            detail=f"Agent invocation failed: {type(exc).__name__}: {exc}",
        ) from exc
