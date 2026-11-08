from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["dev", "test", "prod"] = "dev"
    database_url: str | None = None

    xai_api_key: str | None = None
    xai_model: str = "grok-4.7"
    the_muse_api_key: str | None = None

    gmail_credentials_file: Path = Path("secrets/gmail_client.json")
    gmail_token_file: Path = Path("secrets/gmail_token.json")
    courier_poll_seconds: int = 300

    readai_webhook_secret: str | None = None

    chrome_profile_dir: Path = Path(".chrome-profile")
    chrome_headless: bool = True

    data_dir: Path = Path("data")
    ui_dir: Path = Path("frontend/build")
    scout_max_cases: int = 20

    @property
    def uses_postgres(self) -> bool:
        return self.app_env != "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
