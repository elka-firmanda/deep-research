from pydantic_settings import BaseSettings
from typing import Optional, Literal
from functools import lru_cache


class Settings(BaseSettings):
    # App settings
    app_name: str = "AI Agent"
    debug: bool = False
    settings_file: str = "/app/settings.json"

    # API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    serpapi_api_key: Optional[str] = None

    # Default LLM settings
    default_provider: str = "openai"  # openai, anthropic, openrouter
    default_model: Optional[str] = None

    # OpenRouter settings
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Database settings
    db_type: Literal["sqlite", "postgres"] = "sqlite"
    db_path: str = "/app/data/chat_history.db"  # For SQLite

    # PostgreSQL settings
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "ai_agent"
    postgres_user: str = "postgres"
    postgres_password: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
