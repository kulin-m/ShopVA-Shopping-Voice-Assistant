from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Voice Shopping Assistant"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"

    # Server settings (dynamic PORT for Render / PaaS deployment)
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = int(os.getenv("PORT", "8000"))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-voice-shopping-assistant-2026")
    FRONTEND_URL: Optional[str] = os.getenv("FRONTEND_URL", None)

    # Groq API Configuration
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY", None)
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    # Supabase / PostgreSQL Database Settings
    SUPABASE_URL: Optional[str] = os.getenv("SUPABASE_URL", None)
    SUPABASE_KEY: Optional[str] = os.getenv("SUPABASE_KEY", None)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./voice_shopping.db")

    # Qdrant Vector Search Settings
    QDRANT_URL: Optional[str] = os.getenv("QDRANT_URL", None)
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY", None)
    QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME", "products")

    # Business Logic Thresholds
    SIZE_PREFERENCE_THRESHOLD: int = 2
    HISTORY_LIST_COUNT: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
