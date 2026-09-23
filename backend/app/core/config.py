import os
from typing import List, Optional
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Vault"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    ALLOW_PUBLIC_GALLERY: bool = False

    # Security & Tokens
    SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION_SUPER_SECRET_VAULT_KEY_2026_A98F71B3"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Short-lived access token
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7    # Long-lived refresh token
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost",
        "http://127.0.0.1",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # Database Settings
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "vault_app"
    POSTGRES_PASSWORD: str = "vault_secure_password"
    POSTGRES_DB: str = "vault"
    DATABASE_URL: Optional[str] = None

    @property
    def sync_database_url(self) -> str:
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("sqlite"):
                return self.DATABASE_URL
            return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        if self.POSTGRES_SERVER in ["localhost", "127.0.0.1", "none", "", "sqlite"]:
            os.makedirs(self.STORAGE_LOCAL_ROOT, exist_ok=True)
            db_path = os.path.abspath(os.path.join(self.STORAGE_LOCAL_ROOT, "vault.db"))
            return f"sqlite:///{db_path}"
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Storage Settings
    STORAGE_TYPE: str = "local"  # "local" or "s3"
    STORAGE_LOCAL_ROOT: str = "./storage_data"
    STORAGE_MAX_FILE_SIZE_MB: int = 25
    ALLOWED_IMAGE_MIME_TYPES: List[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    ]
    THUMBNAIL_MAX_SIZE: tuple[int, int] = (400, 400)

    # S3 / MinIO Settings (Future compatibility)
    S3_ENDPOINT_URL: Optional[str] = None
    S3_BUCKET_NAME: Optional[str] = "vault-storage"
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None
    S3_REGION: Optional[str] = "us-east-1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
