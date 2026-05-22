from pydantic_settings import BaseSettings
from pathlib import Path
import os

class Settings(BaseSettings):
    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = False
    
    # Security
    API_KEY: str = "mcp-secret-key-12345"  # Override with .env
    ENABLE_ENCRYPTION: bool = True
    ENCRYPTION_KEY: str = ""  # Will generate if empty
    
    # Storage
    STORAGE_PATH: Path = Path("./storage")
    TEMP_PATH: Path = Path("/tmp/mcp-documents")
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    
    # Features
    ENABLE_CACHING: bool = True
    ENABLE_RAG_EMBEDDINGS: bool = True
    BATCH_SIZE: int = 5
    TIMEOUT_SECONDS: int = 30
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # "json" or "text"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
