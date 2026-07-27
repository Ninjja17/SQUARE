from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # IBM watsonx (kept for Orchestrate auth)
    WATSONX_API_KEY: str = ""
    WATSONX_PROJECT_ID: str = ""
    WATSONX_URL: str = "https://eu-de.ml.cloud.ibm.com"
    GRANITE_MODEL_ID: str = "ibm/granite-13b-instruct-v2"

    # Groq (LLM provider)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # IBM watsonx Orchestrate
    ORCHESTRATE_INSTANCE_URL: str = ""
    ORCHESTRATE_API_KEY: str = ""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/square"

    # ChromaDB
    CHROMA_DB_PATH: str = "./chroma_data"
    CHROMA_DB_URL: str = ""  # if using hosted Chroma

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # App
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    SESSION_EXPIRE_HOURS: int = 24

    # Rate limiting
    RATE_LIMIT_PER_HOUR: int = 5
    MAX_WORKFLOW_DESCRIPTION_LENGTH: int = 2000

    # App mode
    DEMO_MODE: bool = True  # if True, return seeded mock data instead of calling watsonx

    # Admin dashboard (internal use only — never expose this value in responses)
    ADMIN_DASHBOARD_TOKEN: str = "change-me-admin-token"

    class Config:
        env_file = str(_ENV_FILE)
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
