from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    github_app_id: int = 0
    github_webhook_secret: str = "change-me"  # noqa: S105 (dev default)
    github_private_key_path: str = "./secrets/sentinel.private-key.pem"
    github_api_url: str = "https://api.github.com"

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql://sentinel:sentinel@localhost:5432/sentinel"

    litellm_base_url: str = "http://localhost:4000"
    litellm_api_key: str = "sk-local-dev"
    sentinel_model: str = "reviewer"  # a LiteLLM alias: the config decides which real model
    sentinel_reasoning_effort: str = ""

    sentinel_min_confidence: float = 0.6
    sentinel_max_comments: int = 8

    sentinel_max_iterations: int = 4
    sentinel_max_cost_usd: float = 0.50

    sandbox_namespace: str = "sentinel-sandbox"
    sandbox_image: str = "python:3.12-slim"


@lru_cache
def get_settings() -> Settings:
    return Settings()
