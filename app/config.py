import secrets
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: Literal["production", "development"] = "development"
    public_base_url: str = "http://localhost:8000"
    db_path: str = "./data/reliefsync.db"
    salt: str = ""
    coordinator_token: str = ""
    demo_mode: bool = True
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    telegram_mode: Literal["polling", "webhook"] = "polling"
    telegram_webhook_secret: str = ""
    telegram_ack_mode: Literal["short", "off"] = "short"
    test_group_url: str = ""
    feedback_url: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_json_mode: bool = True
    llm_timeout_s: float = Field(20, gt=0, le=120)
    llm_concurrency: int = Field(4, ge=1, le=16)
    allow_fallback_extractor: bool = True
    geocoder_user_agent: str = ""
    geocoder_url: str = ""
    match_radius_km: float = Field(3, gt=0, le=50)
    match_min_score: float = Field(0.5, ge=0, le=1)
    dedupe_window_min: int = Field(120, ge=1)
    log_level: str = "INFO"

    @model_validator(mode="after")
    def validate_secrets(self) -> "Settings":
        if self.app_env == "production" and (len(self.salt) < 32 or len(self.coordinator_token) < 24):
            raise ValueError("Production requires SALT >=32 and COORDINATOR_TOKEN >=24 characters")
        if self.telegram_mode == "webhook" and len(self.telegram_webhook_secret) < 24:
            raise ValueError("Webhook mode requires a secret >=24 characters")
        if self.geocoder_url and not self.geocoder_user_agent:
            raise ValueError("Remote geocoding requires an identifying contact User-Agent")
        if not self.salt:
            self.salt = secrets.token_hex(32)
        return self

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)
