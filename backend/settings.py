from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    app_name: str = "TEDDY"
    app_env: str = "development"
    nebius_api_key: str | None = None
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1"
    nebius_model: str | None = None
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
