from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./concord.db"
    app_origin: str = "http://localhost:3000"
    cookie_secure: bool = False
    session_hours: int = 24
    demo_password: str = "concord-demo-2026"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
