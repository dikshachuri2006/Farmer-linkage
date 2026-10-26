import json
import secrets
from typing import List, Optional, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_PLACEHOLDER_SECRET = "CHANGE_THIS_TO_A_SECURE_RANDOM_SECRET_KEY_AT_LEAST_32_CHARS"


class Settings(BaseSettings):
    # Project Info
    PROJECT_NAME: str = "Farmer Market Linkage & Price Discovery API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Security & JWT
    # Minimum 32 chars recommended for HS256
    SECRET_KEY: str = _PLACEHOLDER_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # PostgreSQL Database Settings (Schema owned by Ankita)
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "farmer_linkage_db"
    DATABASE_URL: Optional[str] = None

    # CORS Frontend Access (For Diksha's Frontend)
    ALLOWED_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5500",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5500",
        "http://127.0.0.1:8080",
    ]

    # Transport & Pricing defaults
    DEFAULT_TRANSPORT_RATE_PER_KM_PER_KG: float = 0.05
    BASE_TRANSPORT_CHARGE: float = 150.0
    MAPS_API_KEY: Optional[str] = None

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, str) and v.startswith("["):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
        return v if isinstance(v, list) else []

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Returns the PostgreSQL connection string using psycopg driver."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        from urllib.parse import quote_plus
        user = quote_plus(str(self.POSTGRES_USER))
        password = quote_plus(str(self.POSTGRES_PASSWORD))
        return (
            f"postgresql+psycopg://{user}:{password}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @model_validator(mode="after")
    def validate_runtime_security(self):
        environment = self.ENVIRONMENT.strip().lower()
        if environment in {"production", "prod", "demo", "staging"}:
            if self.SECRET_KEY == _PLACEHOLDER_SECRET or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "SECRET_KEY must be explicitly configured with at least 32 characters "
                    "outside development."
                )
            if self.DEBUG:
                raise ValueError("DEBUG must be disabled outside development.")
        elif self.SECRET_KEY == _PLACEHOLDER_SECRET:
            # Use a process-local key for development so the published placeholder
            # cannot be used to mint tokens. Restarting invalidates dev tokens.
            self.SECRET_KEY = secrets.token_urlsafe(48)
        return self

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
