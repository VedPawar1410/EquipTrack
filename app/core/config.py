from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration, read from environment variables (or a local .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    sql_echo: bool = False

    # Auth. No default secret on purpose: the app refuses to start without one,
    # so a forgotten env var can never mean "signed with a well-known dev key" in production.
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Documents / RAG
    max_upload_mb: int = 10
    # "fastembed" = real local model (CPU, ONNX). "hashing" = deterministic fake used by the tests.
    embedding_provider: Literal["fastembed", "hashing"] = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"   # 384 dimensions, English
    fastembed_cache_dir: str | None = None              # the Docker image bakes the model in here

    # Retrieval
    rag_top_k: int = 5                 # chunks given to the LLM
    rag_min_similarity: float = 0.55   # below this, a chunk with no exact code match is "not relevant"

    # LLMs: free tiers, tried in order; with none available the API answers with manual excerpts.
    llm_order: str = "groq,gemini"
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"       # pinned, never a "-latest" alias
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    llm_timeout_seconds: float = 30

    @field_validator("groq_api_key", "gemini_api_key", mode="before")
    @classmethod
    def blank_key_means_none(cls, value):
        return value or None


settings = Settings()
