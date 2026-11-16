from typing import Literal

from pydantic import Field
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


settings = Settings()
