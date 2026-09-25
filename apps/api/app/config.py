from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    api_port: int = 8000
    web_origin: str = "http://localhost:5173"
    database_url: str = "postgresql+asyncpg://adpilot:adpilot@localhost:5432/adpilot"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "development-only-change-me"
    storage_dir: str = "./storage"
    auth_db_path: str = "./storage/adpilot.db"
    session_cookie_name: str = "adpilot_session"
    session_ttl_days: int = 7
    ai_api_key: str = ""
    ai_provider: str = "mock"
    live_external_apis: bool = False
    meta_client_id: str = ""
    meta_client_secret: str = ""
    meta_redirect_uri: str = "http://localhost:8000/api/v1/platforms/meta/callback"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/platforms/google/callback"

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
