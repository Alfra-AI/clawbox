"""Configuration settings for AgentBox."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql://agentbox:agentbox@localhost:5432/agentbox"

    # Storage
    storage_backend: str = "local"  # "local" or "s3"
    local_storage_path: Path = Path("./data")

    # AWS / S3
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_bucket_name: str = ""

    # Token settings
    default_storage_limit_bytes: int = 1024 * 1024 * 1024  # 1 GB

    # OpenAI
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    session_secret_key: str = "change-me-to-a-random-string"
    app_url: str = "http://localhost:8000"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
