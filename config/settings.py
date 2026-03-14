"""Application settings and configuration."""

from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Project
    project_name: str = "MEGA QUIXAI"
    environment: str = "development"
    debug: bool = False

    # Database
    database_url: str = "postgresql://user:password@localhost:5432/quixai"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None

    # LLM
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-4-1"
    llm_max_tokens: int = 500
    llm_temperature: float = 0.7

    # RAG
    embedding_model: str = "sentence-transformers/paraphrase-MiniLM-L6-v2"
    rag_top_k: int = 5
    rag_threshold: float = 0.5

    # Stripe
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    api_domain: str = "http://localhost:8000"

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = ""

    # LangFuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4

    # Agent Configuration
    agent_loop_interval: int = 60  # seconds
    agent_max_retries: int = 3
    agent_retry_backoff_multiplier: float = 2.0

    # Closing Agent
    closing_max_conversation_turns: int = 10
    closing_response_timeout: int = 86400  # 24 hours
    closing_offer_expiry_hours: int = 24

    class Config:
        """Pydantic config."""

        env_file = ".env"
        case_sensitive = False

    def get_database_url(self) -> str:
        """Get database URL."""
        return self.database_url

    def get_redis_url(self) -> str:
        """Get Redis URL."""
        password_part = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{password_part}{self.redis_host}:{self.redis_port}/{self.redis_db}"


settings = Settings()
