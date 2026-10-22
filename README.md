# To Run backend 
uv sync
uv run uvicorn agent.api:app --reload --app-dir src --port 8000

# Optional Langfuse tracing
# Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in .env. Traces are emitted
# when both are set and flushed when the FastAPI app shuts down. Trace content
# is masked by default; set LANGFUSE_CAPTURE_CONTENT=true only if storing
# prompts and completions in Langfuse is appropriate for your data policy.

# To Run frontend
cd frontend
npm install
npm run dev