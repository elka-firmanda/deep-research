from pydantic_settings import BaseSettings
from typing import Optional
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

    # Default LLM settings
    default_provider: str = "openai"  # openai, anthropic, openrouter
    default_model: Optional[str] = None

    # OpenRouter settings
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
