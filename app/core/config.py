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


settings = Settings()
