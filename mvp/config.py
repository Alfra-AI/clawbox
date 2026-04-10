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

    # S3-compatible storage (AWS S3, MinIO, GCS, Azure Blob, DO Spaces, etc.)
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_bucket_name: str = ""
    s3_endpoint_url: str = ""  # Leave empty for AWS S3, set for MinIO/GCS/etc.

    # Token settings
    default_storage_limit_bytes: int = 1024 * 1024 * 1024  # 1 GB

    # OpenAI (legacy, kept for backward compat)
    openai_api_key: str = ""

    # Google Gemini (primary embedding provider)
    google_api_key: str = ""
    embedding_model: str = "gemini-embedding-2-preview"
    embedding_dimensions: int = 768
    image_caption_model: str = "gemini-3-flash-preview"

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
