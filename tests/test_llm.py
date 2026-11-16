"""Building the provider chain from settings. Constructing a chat model makes no network call."""
from pydantic import SecretStr

from app.core.config import settings
from app.services import llm


def _build(monkeypatch, **overrides):
    for key, value in overrides.items():
        monkeypatch.setattr(settings, key, value)
    llm.get_chat_model.cache_clear()
    try:
        return llm.get_chat_model()
    finally:
        llm.get_chat_model.cache_clear()


def test_no_keys_means_no_model(monkeypatch):
    assert _build(monkeypatch, groq_api_key=None, gemini_api_key=None) is None


def test_order_and_fallbacks_follow_settings(monkeypatch):
    chain = _build(monkeypatch, groq_api_key=SecretStr("g"), gemini_api_key=SecretStr("m"), llm_order="gemini,groq")
    assert type(chain.runnable).__name__ == "ChatGoogleGenerativeAI"
    assert [type(f).__name__ for f in chain.fallbacks] == ["ChatGroq"]


def test_single_provider_has_no_fallback_wrapper(monkeypatch):
    model = _build(monkeypatch, groq_api_key=SecretStr("g"), gemini_api_key=None)
    assert type(model).__name__ == "ChatGroq" and model.model_name == settings.groq_model


def test_blank_key_counts_as_missing():
    from app.core.config import Settings
    assert Settings(groq_api_key="", database_url="postgresql+asyncpg://u:p@h/db", jwt_secret_key="k" * 32).groq_api_key is None
