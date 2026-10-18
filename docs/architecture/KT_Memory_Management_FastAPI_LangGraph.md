# Knowledge Transfer (KT): Memory Management FastAPI + LangGraph

## 1. Project Overview

This repository exposes a LangGraph memory-management agent through a FastAPI HTTP API.

At a high level:

1. A client sends a chat request to FastAPI.
2. FastAPI validates the request.
3. The API creates LangGraph configuration using a `user_id` and `thread_id`.
4. The compiled LangGraph agent processes the message.
5. The API returns the final assistant response as JSON.

The project uses two kinds of persistence:

- **Checkpointing** — saves graph/conversation state associated with a conversation thread.
- **Long-term memory store** — allows the graph to save and retrieve user-level memories across conversations, when the graph explicitly implements that behavior.

> Important: Passing `user_id` into LangGraph configuration does not automatically create, save, or retrieve long-term memories. The graph's nodes must explicitly use the store for memory operations.

## 2. Technology Stack

- Python
- `uv` for Python project/dependency management
- FastAPI for HTTP endpoints
- Uvicorn as the ASGI server
- LangGraph for agent workflow, state, and checkpointing
- LangChain message types, including `HumanMessage`
- SQLite persistence (based on the current local setup)

Check `pyproject.toml` for the exact dependency declarations and versions.

## 3. Repository Structure

The confirmed application entry point is `src/agent/api.py`. The exact complete repository tree should be verified against the current checkout.

A typical layout for the files discussed in this KT is:

```text
memory-management-fastapi/
├── src/
│   └── agent/
│       ├── api.py              # FastAPI app and HTTP endpoints
│       ├── graph.py            # Builds/compiles the LangGraph graph
│       ├── checkpointer.py     # Creates checkpoint persistence
│       └── store.py            # Creates long-term memory store
├── pyproject.toml              # Project metadata and dependencies
├── uv.lock                     # Locked dependency versions (if tracked)
├── checkpoints.sqlite           # Local checkpoint DB (may be generated)
└── long_term_memory.sqlite     # Local memory DB (may be generated)
```

The names and locations of files other than `src/agent/api.py` are based on the code discussed and should be checked against the actual repository.

## 4. Local Setup

### Prerequisites

- Python version compatible with `pyproject.toml`
- `uv`
- A terminal such as PowerShell
- Required model/provider credentials, if the agent's LLM configuration needs them

### Install dependencies

From the repository root:

```powershell
uv sync
```

If the project uses a `.env` file, create it from the project's documented example and add the required credentials locally. Never commit secrets to Git.

### Start the API

From the repository root, the command confirmed to work in the current setup is:

```powershell
uv run uvicorn agent.api:app --app-dir src --reload
```

- `agent.api:app` means: import the `app` object from `src/agent/api.py`.
- `--app-dir src` tells Uvicorn to include `src` when resolving the `agent` package.
- `--reload` restarts the development server when source files change. Do not use reload mode as a production deployment setting.

The API is normally available at `http://127.0.0.1:8000`.

Interactive API documentation is normally available at `http://127.0.0.1:8000/docs`.

## 5. API Endpoints

### `GET /health`

Purpose: basic health check.

Example:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

This endpoint confirms that the HTTP application is responding. It does not necessarily prove that the LLM provider, database, or every downstream dependency is healthy.

### `POST /chat`

Purpose: send a message to the LangGraph agent.

Request body:

```json
{
  "user_id": "user-1",
  "thread_id": "chat-1",
  "message": "Hello, who are you?"
}
```

PowerShell example:

```powershell
$body = @{
    user_id = "user-1"
    thread_id = "chat-1"
    message = "Hello, who are you?"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/chat" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

The response model is:

```json
{
  "user_id": "user-1",
  "thread_id": "chat-1",
  "answer": "The assistant response appears here."
}
```

The exact `answer` depends on the configured model and graph.

## 6. Request Flow

```text
HTTP client
    |
    v
POST /chat
    |
    v
Pydantic validates ChatRequest
    |
    v
Trim and validate user_id, thread_id, message
    |
    v
Build LangGraph config
    |
    v
app.state.graph.invoke(...)
    |
    v
LangGraph executes nodes and uses persistence
    |
    v
Extract final message content
    |
    v
Return ChatResponse JSON
```

The request schema limits the lengths of `user_id`, `thread_id`, and `message`. The endpoint also strips whitespace and rejects values that become empty.

## 7. Important Code Concepts

### 7.1 FastAPI application and lifespan

The application uses a lifespan context manager to initialize resources during startup and clean them up during shutdown.

Simplified pattern:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Open persistence resources.
    # Build the graph and save it on app.state.
    yield
    # Cleanup after yield runs during shutdown.
```

- Code before `yield`: startup initialization.
- `yield`: hands control to FastAPI so it can serve requests.
- Code after `yield`: shutdown work.
- Context managers also clean up their managed resources when the lifespan exits.

The graph is created during application startup rather than being rebuilt for every request.

### 7.2 `app.state.graph`

The compiled graph is stored on `app.state.graph` so endpoint functions can access the initialized graph.

```python
app.state.graph = build_graph(
    checkpointer=checkpointer,
    store=store,
)
```

### 7.3 `user_id` versus `thread_id`

```python
config = {
    "configurable": {
        "thread_id": thread_id,
        "user_id": user_id,
    }
}
```

- `thread_id`: identifies a conversation thread for checkpointed graph state.
- `user_id`: identifies the user for graph logic, such as namespacing long-term memories.

A single user can have multiple thread IDs. Separate thread IDs normally have separate checkpoint histories. The graph may still retrieve the same user's long-term memories across those threads if the graph explicitly uses a shared user-specific namespace.

### 7.4 Invoking the graph

```python
result = app.state.graph.invoke(
    {"messages": [HumanMessage(content=message)]},
    config=config,
)
```

- `HumanMessage(content=message)` represents the user's message.
- `{"messages": [...]}` supplies input state to the graph.
- `config` passes runtime configuration, including the thread and user identifiers.
- `invoke()` runs the graph synchronously and returns its resulting state.

The endpoint reads the last message's `content` as the answer. This relies on the graph returning messages with the assistant's final response at the end.

### 7.5 Checkpointer versus long-term store

| Component | Intended purpose | Typical scope |
|---|---|---|
| Checkpointer | Save and resume graph/conversation state | One `thread_id` |
| Long-term store | Save and retrieve durable user memories | Often one `user_id` or user-specific namespace |

These are related but different mechanisms. Checkpointing alone does not implement a complete long-term memory strategy.

### 7.6 `graph_lock`

The current API code uses a process-local `threading.Lock` around `graph.invoke()`:

```python
with graph_lock:
    result = app.state.graph.invoke(...)
```

This serializes graph invocations that pass through this lock in the same process. It can reduce concurrent throughput. It does not coordinate across multiple worker processes or multiple server instances, and it does not replace database transactions or a production concurrency strategy.

## 8. Persistence and Local Data

The current API code resolves the project root from `api.py` and uses database files named:

- `checkpoints.sqlite`
- `long_term_memory.sqlite`

These files may be created when the persistence components initialize. Confirm the exact storage implementation in `checkpointer.py` and `store.py`.

Operational notes:

- Do not delete the SQLite files if you need to retain local conversation state or memories.
- Do not assume local SQLite files are suitable for a multi-instance production deployment.
- Back up persistent data before migration or destructive changes.
- Keep database files and secrets out of source control where appropriate.

## 9. Error Handling and Logging

The endpoint logs request start/completion and logs invocation failures with a traceback. It validates input and returns HTTP errors when inputs are invalid or graph invocation fails.

Before production, review the error response. The current development version may include exception details in the HTTP 500 response; public production APIs should generally return a generic client-facing error while logging detailed diagnostics securely on the server.

## 10. Running and Testing Checklist

1. Open a terminal at the repository root.
2. Run `uv sync`.
3. Configure required environment variables or `.env` locally.
4. Start the server with the Uvicorn command above.
5. Open `http://127.0.0.1:8000/docs`.
6. Call `GET /health`.
7. Call `POST /chat` with a `user_id`, `thread_id`, and `message`.
8. Send another message with the same `thread_id` to test thread continuity.
9. Send a message with a different `thread_id` to test separate checkpoint history.
10. Inspect the graph implementation to verify whether long-term memories are actually written and retrieved.

## 11. Production Readiness Checklist

Before exposing this API to real users, review the following:

- [ ] Authenticate callers.
- [ ] Derive or validate `user_id` from authenticated identity instead of trusting arbitrary client-supplied IDs.
- [ ] Authorize access to each conversation thread and its memories.
- [ ] Avoid returning raw exception messages to clients.
- [ ] Confirm that graph, checkpointer, and store access are safe under the intended concurrency model.
- [ ] Reassess the process-local `threading.Lock` and its throughput impact.
- [ ] Choose persistence suitable for the deployment topology and backup requirements.
- [ ] Keep API keys and other secrets out of source control.
- [ ] Configure timeouts, resource limits, and observability.
- [ ] Add automated tests for validation, health, graph success/failure, checkpoint continuity, and memory behavior.
- [ ] Use a production ASGI process configuration rather than development reload mode.
- [ ] Add dependency and database migration procedures where needed.

## 12. Suggested KT Walkthrough

A teammate should be able to follow this order:

1. **Repository setup** — explain `uv sync`, environment configuration, and the run command.
2. **API entry point** — walk through `src/agent/api.py`.
3. **Lifespan** — explain resource initialization, `yield`, and cleanup.
4. **Request models** — explain `ChatRequest` and `ChatResponse`.
5. **Request flow** — follow a request through `/chat` to `graph.invoke()`.
6. **Graph configuration** — explain `user_id` and `thread_id`.
7. **Persistence** — explain the checkpointer and long-term store.
8. **Memory behavior** — trace where the graph writes memories and where it retrieves them.
9. **Testing** — exercise `/health`, `/docs`, and `/chat`.
10. **Production gaps** — discuss authentication, errors, concurrency, storage, and monitoring.

## 13. Useful Commands

```powershell
# Install/synchronize dependencies
uv sync

# Start development server
uv run uvicorn agent.api:app --app-dir src --reload

# Run tests, if pytest and tests are configured
uv run pytest
```

## 14. Key Takeaways

- FastAPI provides the HTTP interface; LangGraph runs the agent workflow.
- The lifespan initializes persistence resources and compiles the graph.
- `app.state.graph` makes the initialized graph available to request handlers.
- `thread_id` separates checkpointed conversation histories.
- `user_id` can scope long-term memory, but the graph must implement memory reads and writes.
- A checkpointer and a long-term store serve different purposes.
- The current local SQLite and process-local lock setup should be reviewed before multi-worker or multi-instance production deployment.

---
**KT document note:** This document reflects the implementation details discussed for the repository. Verify filenames, dependency versions, memory node behavior, and persistence backend against the current checkout before using it as an authoritative production runbook.
