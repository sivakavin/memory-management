# Production Agentic AI Memory — Workflow

This document describes the workflow for a decoupled Agentic AI application using LangGraph, a separate memory service, and PostgreSQL.

## Workflow diagram

```mermaid
flowchart TD
    USER["User / Client"]
    API["FastAPI Endpoint"]
    AUTH["Authentication and User Validation"]
    AGENT["Agent Service - LangGraph"]
    STATE["Load Conversation State"]
    STM[("Short-Term Memory<br/>PostgreSQL Checkpointer")]
    RETRIEVE["Memory Service - Retrieve Relevant Memories"]
    LTM[("Long-Term Memory<br/>PostgreSQL")]
    PROMPT["Build LLM Context<br/>System Prompt + History + Memories"]
    LLM["ChatGroq LLM"]
    RESPONSE["Return Response to User"]
    EXTRACT["Memory Extraction and Classification"]
    VALIDATE["Validate, Deduplicate and Update"]
    ROUTE{"Memory Type"}
    SEM["Semantic Memory<br/>Facts and Preferences"]
    EPI["Episodic Memory<br/>Events and Outcomes"]
    PROC["Procedural Memory<br/>Reusable Steps"]
    OBS["Logging, Tracing and Evaluation"]

    USER --> API
    API --> AUTH
    AUTH --> AGENT
    AGENT --> STATE
    STATE <--> STM
    STATE --> RETRIEVE
    RETRIEVE <--> LTM
    RETRIEVE --> PROMPT
    PROMPT --> LLM
    LLM --> RESPONSE
    LLM --> EXTRACT
    EXTRACT --> VALIDATE
    VALIDATE --> ROUTE
    ROUTE --> SEM
    ROUTE --> EPI
    ROUTE --> PROC
    SEM --> LTM
    EPI --> LTM
    PROC --> LTM

    API -.-> OBS
    AGENT -.-> OBS
    LLM -.-> OBS
    VALIDATE -.-> OBS
```

## Workflow overview

1. **Request and identity:** The API authenticates the caller and establishes the authorized user ID and conversation/thread ID.
2. **Conversation state:** LangGraph loads and updates short-term state through a PostgreSQL checkpointer, keyed by thread.
3. **Memory retrieval:** The memory service retrieves relevant long-term memories scoped to the authorized user.
4. **Context assembly:** The agent combines the system prompt, conversation state, and selected memories.
5. **LLM response:** The model generates a response, which the API returns to the user.
6. **Memory extraction:** A memory-extraction step identifies candidate facts, events, and reusable procedures from appropriate conversation/task data.
7. **Validation and persistence:** Validate candidates, remove duplicates, handle updates/conflicts, apply privacy rules, and save accepted memories.
8. **Observability:** Record safe operational logs, traces, errors, and evaluation results without exposing secrets or unnecessary sensitive content.

## Long-term memory types

- **Semantic memory:** Stable facts and preferences.
- **Episodic memory:** Specific events, actions, and outcomes.
- **Procedural memory:** Reusable instructions, workflows, and successful methods.

These are logical memory categories; they can be stored in the same PostgreSQL database using a `memory_type` field and suitable metadata.

## Design notes

- Keep agent orchestration and memory persistence in separate modules.
- Use a durable PostgreSQL checkpointer for short-term conversation state.
- Use a separate repository/service for long-term memory CRUD and retrieval.
- Enforce authorization and user-level data isolation on every memory operation.
- Treat extracted memories as untrusted candidates; validate before storing.
- Add migrations, retries, timeouts, tests, backups, and retention/deletion policies.
- Add vector embeddings and semantic similarity search only when needed; exact metadata filters may be sufficient initially.
- For asynchronous memory extraction, use a reliable queue/job mechanism and track failures so updates are not silently lost.

## Suggested repository location

Save this file as:

`docs/architecture/workflow.md`
