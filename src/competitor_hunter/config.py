"""Configuration management using Pydantic Settings."""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenAI API Configuration
    openai_api_key: str = Field(
        ...,
        description="OpenAI API key for LLM operations",
        validation_alias="OPENAI_API_KEY",
    )
    openai_base_url: Optional[str] = Field(
        default=None,
        description="OpenAI API base URL (for custom endpoints)",
        validation_alias="OPENAI_BASE_URL",
    )
    openai_model_name: str = Field(
        default="gpt-4o",
        description="OpenAI model name to use",
        validation_alias="OPENAI_MODEL_NAME",
    )

    # Browser Configuration
    headless_mode: bool = Field(
        default=True,
        description="Run browser in headless mode",
        validation_alias="HEADLESS_MODE",
    )

    # Database Configuration
    db_path: Path = Field(
        default=Path("data/competitors.db"),
        description="Path to SQLite database file",
        validation_alias="DB_PATH",
    )

    def model_post_init(self, __context) -> None:
        """Ensure database directory exists."""
        if self.db_path:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()

