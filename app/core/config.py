"""Application settings loaded from environment variables."""

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]

for env_file in (BASE_DIR / ".env.development", BASE_DIR / ".env", BASE_DIR / ".env.example"):
    if env_file.is_file():
        load_dotenv(env_file, override=False)
        break


class Settings(BaseSettings):
    """Runtime configuration for the RAG service."""

    model_config = SettingsConfigDict(extra="ignore")

    PROJECT_NAME: str = "LOGFLOWS Knowledge RAG"
    DEBUG: bool = False
    ALLOWED_ORIGINS: str = "*"

    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str | None = None
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_MODEL: str = "gpt-4.1-mini"
    LLM_TEMPERATURE: float = 0.0

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "ragdb"
    POSTGRES_USER: str = "raguser"
    POSTGRES_PASSWORD: str = "ragpassword"

    CHUNK_SIZE: int = 900
    CHUNK_OVERLAP: int = 120
    RETRIEVE_K: int = 6
    EVIDENCE_THRESHOLD: float = 0.22
    HIGH_CONFIDENCE_THRESHOLD: float = 0.45

    @property
    def cors_origins(self) -> list[str]:
        """Parse comma-separated CORS origins; `*` means any frontend."""
        raw = self.ALLOWED_ORIGINS.strip()
        if raw == "*":
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def postgres_dsn(self) -> str:
        """Async Postgres DSN for psycopg."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
