from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    app_name: str = "TEDDY"
    app_env: str = "development"
    nebius_api_key: str | None = None
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1"
    nebius_model: str | None = None
    # Fable is opt-in to avoid unexpected paid inference calls.
    anthropic_api_key: str | None = None
    claude_fable_model: str = "claude-fable-5-1"
    claude_fable_enabled: bool = False
    claude_fable_max_output_tokens: int = 900
    claude_fable_max_prompt_chars: int = 8000
    claude_fable_max_estimated_cost_usd: float = 0.10
    sqlite_path: str = "./data/teddy.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def nebius_ready(self) -> bool:
        return bool(self.nebius_api_key and self.nebius_model)

    @property
    def claude_fable_ready(self) -> bool:
        return bool(self.claude_fable_enabled and self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
