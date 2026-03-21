from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _clean_settings_env() -> None:
    """Nettoie les variables d'env et le cache get_settings après chaque test.

    Évite la pollution entre tests quand cli.py modifie os.environ
    (ex: NOTEBOOK_NAME via --notebook) et vide le lru_cache de get_settings.
    """
    yield
    # Supprimer les variables d'env injectées par cli.py
    os.environ.pop("NOTEBOOK_NAME", None)
    # Vider le cache singleton pour que le prochain test reparte propre
    from src.config import get_settings

    get_settings.cache_clear()
