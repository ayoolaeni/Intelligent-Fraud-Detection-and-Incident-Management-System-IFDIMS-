"""Application settings, read from environment variables (Section 14)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://ifdims:ifdims@db:5432/ifdims"

    jwt_secret: str = "change-me-to-a-long-random-string-of-32-plus-chars"
    jwt_expire_minutes: int = 60

    bvn_salt: str = "change-me"
    phone_salt: str = "change-me"

    service_api_keys: str = "simulator:sim-key-change-me"

    models_dir: str = "./models"
    attachments_dir: str = "./attachments"

    frontend_origin: str = "http://localhost:5173"

    admin_email: str = "admin@ifdims.local"
    admin_password: str = "Admin12345!"
    seed_demo_users: bool = True

    tz: str = "Africa/Lagos"

    @property
    def service_api_keys_map(self) -> dict[str, str]:
        """Parse 'name:key,name2:key2' into {name: key}."""
        result: dict[str, str] = {}
        for pair in self.service_api_keys.split(","):
            pair = pair.strip()
            if not pair:
                continue
            name, _, key = pair.partition(":")
            if name and key:
                result[name] = key
        return result

    def validate_production(self) -> None:
        if self.app_env == "production" and (
            self.jwt_secret == "change-me-to-a-long-random-string-of-32-plus-chars"
            or len(self.jwt_secret) < 32
        ):
            raise RuntimeError(
                "JWT_SECRET must be set to a real, >=32 character random value when APP_ENV=production"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
