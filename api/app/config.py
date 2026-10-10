from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path

# Look for .env in project root or current dir
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

class Settings(BaseSettings):
    APP_NAME: str = "Nexora API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "127.0.0.1"

    # Supabase credentials
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None

    # Storage Buckets
    SUPABASE_BUCKET_THUMBNAILS: str = "course_thumbnails"
    SUPABASE_BUCKET_VIDEOS: str = "videos"
    SUPABASE_BUCKET_AVATARS: str = "profile_images"

    # Auth
    SECRET_KEY: str = "nexora_production_jwt_secret_dev_key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH) if ENV_PATH.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
