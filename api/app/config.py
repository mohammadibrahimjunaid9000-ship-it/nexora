from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path

# Look for api/.env first, then root .env
BASE_DIR = Path(__file__).resolve().parent.parent.parent
API_ENV_PATH = BASE_DIR / "api" / ".env"
ROOT_ENV_PATH = BASE_DIR / ".env"

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

    # Auth & JWT Security
    SECRET_KEY: str = "nexora_production_jwt_secret_dev_key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Auth Cookie Configuration (HttpOnly)
    AUTH_COOKIE_NAME: str = "nexora_access_token"
    AUTH_COOKIE_SECURE: bool = False  # Set to True in production (HTTPS)
    AUTH_COOKIE_SAMESITE: str = "lax"  # 'lax', 'strict', or 'none'
    AUTH_COOKIE_PATH: str = "/"

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @model_validator(mode="after")
    def validate_production_security(self):
        """Enforce strict production secret and cookie requirements when DEBUG is False."""
        if not self.DEBUG:
            insecure_placeholders = {
                "nexora_production_jwt_secret_dev_key",
                "your_super_secret_jwt_key",
                "secret",
                "changeme",
            }
            if not self.SECRET_KEY or self.SECRET_KEY.strip() in insecure_placeholders:
                raise ValueError(
                    "Production deployment requires a secure, non-default SECRET_KEY environment variable."
                )
            if not self.AUTH_COOKIE_SECURE:
                raise ValueError(
                    "Production deployment requires AUTH_COOKIE_SECURE=True for HTTPS transmission."
                )
        return self

    model_config = SettingsConfigDict(
        env_file=str(API_ENV_PATH) if API_ENV_PATH.exists() else (str(ROOT_ENV_PATH) if ROOT_ENV_PATH.exists() else None),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
