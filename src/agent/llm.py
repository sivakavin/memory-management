from langchain_groq import ChatGroq
from agent.config import get_settings

def get_llm() -> ChatGroq:
    settings = get_settings()

    if not settings.groq_api_key:
        raise ValueError(
            "GROQ_API_KEY is missing. Add it to your .env file."
        )
    
    return ChatGroq(
        model=settings.model,
        api_key=settings.groq_api_key,
        temperature=settings.temperature,
    )