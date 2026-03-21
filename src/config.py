"""Configuration via pydantic-settings et variables d'environnement."""

from __future__ import annotations

from functools import cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration de l'application OneNote Exporter."""

    azure_client_id: str = ""
    azure_tenant_id: str = "common"
    notebook_name: str = ""
    export_output_dir: Path = Path("io/exports")
    cache_dir: Path = Path("io/cache")
    graph_rate_limit: int = 4
    cache_ttl_seconds: int = 86400
    max_pages: int = 150

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@cache
def get_settings() -> Settings:
    """Retourne l'instance de configuration (singleton)."""
    return Settings()
