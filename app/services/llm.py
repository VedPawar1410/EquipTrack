"""The LLM layer: LangChain chat models chained with .with_fallbacks().

Only generation goes through LangChain. Retrieval is our own SQL (app/services/retrieval.py),
so the schema stays owned by Liquibase.
"""
from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable

from app.core.config import settings


def _build(provider: str) -> BaseChatModel | None:
    # max_retries=0: on a rate limit or outage, moving to the next provider beats retrying the same one.
    if provider == "groq" and settings.groq_api_key:
        from langchain_groq import ChatGroq
        return ChatGroq(model=settings.groq_model, api_key=settings.groq_api_key, temperature=0.1,
                        max_retries=0, timeout=settings.llm_timeout_seconds)
    if provider == "gemini" and settings.gemini_api_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=settings.gemini_model, google_api_key=settings.gemini_api_key,
                                      temperature=0.1, max_retries=0, timeout=settings.llm_timeout_seconds)
    return None


@lru_cache(maxsize=1)
def get_chat_model() -> Runnable | None:
    """FastAPI dependency. None when no provider key is configured (the API then answers with excerpts)."""
    models = [m for name in settings.llm_order.split(",") if (m := _build(name.strip()))]
    if not models:
        return None
    primary, *fallbacks = models
    return primary.with_fallbacks(fallbacks) if fallbacks else primary
