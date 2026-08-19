"""Application settings loaded from environment variables."""

from pathlib import Path
from urllib.parse import quote, unquote

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

    # OpenRouter is OpenAI-compatible: same /chat/completions and /embeddings paths.
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    EMBEDDING_MODEL: str = "qwen/qwen3-embedding-4b"
    EMBEDDING_DIMENSIONS: int = 1024
    LLM_MODEL: str = "google/gemma-4-26b-a4b-it:free"
    LLM_TEMPERATURE: float = 0.0

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "ragdb"
    POSTGRES_USER: str = "raguser"
    POSTGRES_PASSWORD: str = "ragpassword"
    POSTGRES_SSLMODE: str = "prefer"

    CHUNK_SIZE: int = 900
    CHUNK_OVERLAP: int = 120
    CHUNK_SIZE_TOKENS: int = 256
    CHUNK_OVERLAP_TOKENS: int = 32
    RETRIEVE_K: int = 6
    EXPAND_SECTION_SIBLINGS: bool = True
    RETRIEVE_MAX_EXPANDED: int = 24
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
        """Async Postgres DSN for psycopg (password URL-encoded; SSL for hosted DBs)."""
        user = quote(unquote(self.POSTGRES_USER), safe="")
        password = quote(unquote(self.POSTGRES_PASSWORD), safe="")
        return (
            f"postgresql://{user}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            f"?sslmode={self.POSTGRES_SSLMODE}"
        )


settings = Settings()
