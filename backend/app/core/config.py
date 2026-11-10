"""
Centralised application configuration for VulnForge.

Architecture Decision:
    All configuration is sourced from environment variables via
    Pydantic's ``BaseSettings``.  There are ZERO hardcoded values.

    ``get_settings()`` is cached with ``@lru_cache`` so the env is only
    parsed once per process — fast and safe to call from any module.

    The ``database_url`` and ``redis_url`` properties are *assembled*
    from their component parts rather than being directly settable.  This
    prevents the "partially configured" footgun where URL and individual
    host/port env vars conflict with each other.

Usage:
    from app.core.config import get_settings

    settings = get_settings()
    print(settings.database_url)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """VulnForge application settings.

    All values are loaded from environment variables.  The field names map
    directly to the variable names in ``.env`` / ``.env.example``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ignore unknown env vars silently
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = Field(default="VulnForge", description="Application display name.")
    app_version: str = Field(default="0.1.0", description="Semantic version string.")
    app_env: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment.",
    )
    debug: bool = Field(default=False, description="Enable debug mode. NEVER true in production.")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level.",
    )
    log_format: Literal["JSON", "CONSOLE"] = Field(
        default="CONSOLE",
        description="Log output format. Use JSON in production.",
    )

    # ── API Server ────────────────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0", description="Uvicorn bind host.")
    api_port: int = Field(default=8000, ge=1, le=65535, description="Uvicorn bind port.")
    api_prefix: str = Field(default="/api", description="Global API route prefix.")
    api_v1_prefix: str = Field(default="/api/v1", description="v1 API route prefix.")
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="CORS allowed origins.",
    )

    # ── Security ──────────────────────────────────────────────────────────────
    secret_key: str = Field(
        ...,
        min_length=32,
        description="HS256 signing key. Generate with: python scripts/generate_secret.py",
    )
    algorithm: str = Field(default="HS256", description="JWT signing algorithm.")
    access_token_expire_minutes: int = Field(
        default=30,
        ge=5,
        le=1440,
        description="Access token TTL in minutes.",
    )
    refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description="Refresh token TTL in days.",
    )
    password_min_length: int = Field(
        default=12,
        ge=8,
        description="Minimum password length.",
    )
    max_login_attempts: int = Field(
        default=5,
        ge=1,
        description="Failed login attempts before lockout.",
    )
    lockout_duration_minutes: int = Field(
        default=15,
        ge=1,
        description="Account lockout duration after max failed attempts.",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    postgres_host: str = Field(default="localhost", description="PostgreSQL hostname.")
    postgres_port: int = Field(default=5432, ge=1, le=65535, description="PostgreSQL port.")
    postgres_db: str = Field(default="vulnforge", description="PostgreSQL database name.")
    postgres_user: str = Field(default="vulnforge_user", description="PostgreSQL username.")
    postgres_password: str = Field(..., description="PostgreSQL password.")
    db_pool_size: int = Field(default=10, ge=1, description="SQLAlchemy connection pool size.")
    db_max_overflow: int = Field(
        default=20,
        ge=0,
        description="SQLAlchemy pool max overflow connections.",
    )
    db_pool_timeout: int = Field(
        default=30,
        ge=1,
        description="Seconds to wait for a pool connection before raising.",
    )
    db_pool_recycle: int = Field(
        default=1800,
        ge=60,
        description="Seconds after which connections are recycled.",
    )
    db_echo: bool = Field(
        default=False,
        description="Log all SQL statements. NEVER true in production.",
    )

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_host: str = Field(default="localhost", description="Redis hostname.")
    redis_port: int = Field(default=6379, ge=1, le=65535, description="Redis port.")
    redis_db: int = Field(default=0, ge=0, le=15, description="Redis database index.")
    redis_password: str | None = Field(default=None, description="Redis password (optional).")

    # ── Celery ────────────────────────────────────────────────────────────────
    celery_worker_concurrency: int = Field(
        default=4,
        ge=1,
        description="Number of concurrent Celery worker processes.",
    )
    celery_task_soft_time_limit: int = Field(
        default=3600,
        ge=60,
        description="Celery task soft time limit in seconds.",
    )
    celery_task_time_limit: int = Field(
        default=3900,
        ge=61,
        description="Celery task hard time limit in seconds.",
    )
    celery_max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum Celery task retry attempts.",
    )

    # ── Plugin System ─────────────────────────────────────────────────────────
    plugin_execution_timeout: int = Field(
        default=300,
        ge=30,
        description="Maximum seconds a single plugin subprocess may run.",
    )
    plugin_max_concurrent_scans: int = Field(
        default=5,
        ge=1,
        description="Maximum number of scans running simultaneously.",
    )
    plugin_sandbox_enabled: bool = Field(
        default=True,
        description="Enforce subprocess isolation for plugin execution.",
    )
    plugin_output_dir: str = Field(
        default="/tmp/vulnforge/plugin_output",
        description="Directory for plugin subprocess output files.",
    )

    # ── Report Engine ─────────────────────────────────────────────────────────
    report_output_dir: str = Field(
        default="/tmp/vulnforge/reports",
        description="Directory where generated report files are stored.",
    )
    report_max_age_days: int = Field(
        default=90,
        ge=1,
        description="Days after which generated report files are purged.",
    )

    # ── External Tools ────────────────────────────────────────────────────────
    nmap_binary: str = Field(
        default="/usr/bin/nmap",
        description="Absolute path to the nmap executable.",
    )
    nuclei_binary: str = Field(
        default="/usr/local/bin/nuclei",
        description="Absolute path to the nuclei executable.",
    )
    nikto_binary: str = Field(
        default="/usr/bin/nikto",
        description="Absolute path to the nikto executable.",
    )

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_requests: int = Field(
        default=100,
        ge=1,
        description="Maximum requests per rate limit window.",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        ge=1,
        description="Rate limiting window in seconds.",
    )

    # ── First Superuser (seeded on first run) ─────────────────────────────────
    first_superuser_email: str = Field(
        default="admin@vulnforge.com",
        description="Email of the initial superuser account.",
    )
    first_superuser_password: str = Field(
        ...,
        min_length=12,
        description="Password of the initial superuser account.",
    )
    first_superuser_username: str = Field(
        default="admin",
        description="Username of the initial superuser account.",
    )

    # ── RAG / Knowledge Base ──────────────────────────────────────────────────
    voyage_api_key: str | None = Field(
        default=None,
        description="Voyage AI API key for embedding writeups. If unset, a local "
        "deterministic fake embedder is used (dev/offline only).",
    )
    voyage_api_key_fallback: str | None = Field(
        default=None,
        description="Optional second Voyage key. Used only after the primary key's "
        "free-token quota is exhausted (not for transient rate limits).",
    )
    rag_embedding_provider: str = Field(
        default="voyage",
        description="Embedding backend: 'voyage' (falls back to fake if no key) or 'fake'.",
    )
    rag_embedding_model: str = Field(
        default="voyage-3.5-lite",
        description="Voyage embedding model. Commit to one model to avoid re-embeds.",
    )
    rag_embedding_dim: int = Field(
        default=1024,
        ge=64,
        description="Embedding dimensionality. MUST match the Writeup vector column.",
    )
    rag_chunk_size: int = Field(
        default=1200,
        ge=200,
        description="Max characters per writeup chunk before embedding.",
    )
    rag_chunk_overlap: int = Field(
        default=200,
        ge=0,
        description="Character overlap between consecutive chunks.",
    )
    rag_default_top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Default number of writeup chunks returned by a retrieval query.",
    )
    rag_ingest_enabled: bool = Field(
        default=False,
        description="Enable the scheduled writeup ingestion beat task.",
    )
    hackerone_api_token: str | None = Field(
        default=None,
        description="Optional HackerOne API token for authenticated Hacktivity access.",
    )

    # ── Validators ────────────────────────────────────────────────────────────
    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: str | list[str]) -> list[str]:
        """Parse comma-separated CORS origins from a single env var string.

        Args:
            v: A comma-separated string or an already-parsed list.

        Returns:
            list[str]: List of allowed origin strings.
        """
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Enforce security constraints in production environments.

        Raises:
            ValueError: If debug mode or SQL echo is enabled in production.

        Returns:
            Settings: The validated settings instance.
        """
        if self.app_env == "production":
            if self.debug:
                raise ValueError("DEBUG must be False in production.")
            if self.db_echo:
                raise ValueError("DB_ECHO must be False in production.")
            if self.log_format != "JSON":
                raise ValueError("LOG_FORMAT must be JSON in production.")
        return self

    # ── Computed Properties ───────────────────────────────────────────────────
    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> str:
        """Async-compatible PostgreSQL connection URL using asyncpg driver.

        Returns:
            str: Full asyncpg connection URL.
        """
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def database_url_sync(self) -> str:
        """Synchronous PostgreSQL connection URL using psycopg2.

        Used by Alembic's offline migration mode and scripts that do not
        support async connections.

        Returns:
            str: Full psycopg2 connection URL.
        """
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def redis_url(self) -> str:
        """Redis connection URL assembled from component settings.

        Returns:
            str: Full Redis connection URL.
        """
        if self.redis_password:
            return (
                f"redis://:{self.redis_password}"
                f"@{self.redis_host}:{self.redis_port}/{self.redis_db}"
            )
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @computed_field  # type: ignore[misc]
    @property
    def celery_broker_url(self) -> str:
        """Celery broker URL (Redis).

        Returns:
            str: Redis URL for use as Celery broker.
        """
        return self.redis_url

    @computed_field  # type: ignore[misc]
    @property
    def celery_result_backend(self) -> str:
        """Celery result backend URL (Redis).

        Returns:
            str: Redis URL for use as Celery result backend.
        """
        return self.redis_url

    @computed_field  # type: ignore[misc]
    @property
    def is_production(self) -> bool:
        """Return True if running in the production environment.

        Returns:
            bool: True if ``app_env == 'production'``.
        """
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton.

    Using ``lru_cache`` ensures environment variables are only parsed once
    per process, making this safe and efficient to call from any module.

    Returns:
        Settings: The validated, cached settings instance.

    Example:
        >>> from app.core.config import get_settings
        >>> settings = get_settings()
        >>> print(settings.app_name)
        VulnForge
    """
    return Settings()  # type: ignore[call-arg]
