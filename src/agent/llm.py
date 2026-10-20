from langchain_groq import ChatGroq

from agent.config import get_settings


def get_llm(
    api_key: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
) -> ChatGroq:
    """Build a ChatGroq client.

    Values passed in explicitly (for example from the UI) take priority over
    the server-side settings loaded from the environment.
    """
    settings = get_settings()

    resolved_key = (api_key or settings.groq_api_key or "").strip()

    if not resolved_key:
        raise ValueError(
            "GROQ_API_KEY is missing. Add it to your .env file or set it "
            "from the app's LLM settings."
        )

    return ChatGroq(
        model=model or settings.model,
        api_key=resolved_key,
        temperature=(
            temperature if temperature is not None else settings.temperature
        ),
    )
