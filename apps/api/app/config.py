import ssl
from typing import Literal
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    app_env: Literal["development", "production"] = "development"
    database_url: str = "sqlite+aiosqlite:///./concord.db"
    database_ssl: Literal["disable", "verify-full"] = "disable"
    app_origin: str = "http://localhost:3000"
    cookie_secure: bool = False
    session_hours: int = 24
    demo_password: str = "concord-demo-2026"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def database_connect_args(self):
        if self.database_ssl == "verify-full":
            return {"ssl": ssl.create_default_context()}
        return {}

    @model_validator(mode="after")
    def production_settings(self):
        if self.app_env == "production":
            origin = urlsplit(self.app_origin)
            if (
                origin.scheme != "https"
                or not origin.hostname
                or origin.username
                or origin.password
                or origin.path
                or origin.query
                or origin.fragment
            ):
                raise ValueError("Production APP_ORIGIN must be an exact HTTPS origin")
            if not self.cookie_secure:
                raise ValueError("Production requires COOKIE_SECURE=true")
            database = make_url(self.database_url)
            if database.drivername != "postgresql+asyncpg" or len(database.password or "") < 20:
                raise ValueError(
                    "Production requires PostgreSQL and a password of at least 20 characters"
                )
        return self


settings = Settings()
