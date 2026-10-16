from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Palmistry & Tarot Intelligence Platform"
    API_V1_STR: str = "/api/v1"

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # PostgreSQL
    POSTGRES_ASYNC_URI: str

    # MongoDB
    MONGO_URI: str
    MONGO_DB_NAME: str = "spiritual_platform_db"

    # Redis
    REDIS_URI: str = "redis://localhost:6379/0"

    # OpenRouter
    OPENROUTER_API_KEY: str
    OPENROUTER_MODEL: str = "openrouter/free"

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()