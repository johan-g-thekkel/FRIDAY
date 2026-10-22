from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    app_name: str = "FRIDAY"
    app_env: str = "development"

    # Local-first Ollama. A model must be pulled into this runtime before it is usable.
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:1.5b"
    local_stt_model: str = "tiny"

    nebius_api_key: str | None = None
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1"
    nebius_model: str | None = None
    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str | None = None
    openai_compatible_api_key: str | None = None
    openai_compatible_base_url: str | None = None
    openai_compatible_model: str | None = None
    openai_compatible_name: str = "Custom OpenAI-compatible model"
    model_profiles_path: str = "./data/model-profiles.json"

    anthropic_api_key: str | None = None
    claude_fable_model: str = "claude-fable-5-1"
    claude_fable_enabled: bool = False
    claude_fable_max_output_tokens: int = 900
    claude_fable_max_prompt_chars: int = 8000
    claude_fable_max_estimated_cost_usd: float = 0.10

    # Optional cloud speech generation. FRIDAY's new default voice is local browser TTS.
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_model_id: str = "eleven_flash_v2_5"

    sqlite_path: str = "./data/friday.db"
    skills_root: str = "./skills/friday-imported"
    skills_policy_path: str = "./data/skills-policy.json"
    max_active_skills: int = 2
    max_skill_context_chars: int = 6000
    agent_timeout_seconds: int = 900
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
    def nvidia_ready(self) -> bool:
        return bool(self.nvidia_api_key and self.nvidia_model)

    @property
    def openai_compatible_ready(self) -> bool:
        return bool(
            self.openai_compatible_api_key
            and self.openai_compatible_base_url
            and self.openai_compatible_model
        )

    @property
    def claude_fable_ready(self) -> bool:
        return bool(self.claude_fable_enabled and self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
