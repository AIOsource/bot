"""Environment settings with pydantic-settings."""
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment."""
    
    # Telegram
    telegram_bot_token: str = Field(..., description="Telegram Bot API token")
    admin_chat_id: int = Field(..., description="Admin Telegram chat ID")
    
    # OpenRouter LLM
    openrouter_api_key: str = Field(..., description="OpenRouter API key")
    openrouter_model: str = Field(
        default="anthropic/claude-3.5-sonnet",
        description="OpenRouter model name"
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API base URL"
    )
    
    # Application
    app_timezone: str = Field(default="Asia/Yekaterinburg", description="Application timezone")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/prsbot.db",
        description="Database connection URL"
    )
    log_level: str = Field(default="INFO", description="Logging level")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
