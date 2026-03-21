"""Tests pour la configuration."""

import os
from pathlib import Path

from src.config import Settings, get_settings


class TestSettings:
    """Tests pour la classe Settings."""

    def test_default_settings_have_sane_defaults(self) -> None:
        """Les settings par défaut doivent avoir des valeurs raisonnables."""
        settings = Settings(azure_client_id="test-id")
        assert settings.azure_tenant_id == "common"
        assert settings.graph_rate_limit == 4
        assert settings.max_pages == 150
        assert settings.cache_ttl_seconds == 3600

    def test_export_output_dir_is_path(self) -> None:
        """Le dossier d'export doit être un Path."""
        settings = Settings(azure_client_id="test-id")
        assert isinstance(settings.export_output_dir, Path)

    def test_get_settings_returns_settings_instance(self) -> None:
        """get_settings doit retourner une instance Settings."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_returns_same_instance(self) -> None:
        """get_settings doit retourner le même objet (singleton via lru_cache)."""
        from src.config import get_settings as gs

        gs.cache_clear()
        s1 = gs()
        s2 = gs()
        assert s1 is s2

    def test_notebook_name_defaults_to_empty(self) -> None:
        """notebook_name doit être vide par défaut (sans pollution d'env)."""
        saved = os.environ.pop("NOTEBOOK_NAME", None)
        try:
            settings = Settings(azure_client_id="test-id", _env_file=None)
            assert settings.notebook_name == ""
        finally:
            if saved is not None:
                os.environ["NOTEBOOK_NAME"] = saved

    def test_notebook_name_accepts_string(self) -> None:
        """notebook_name doit accepter un nom de notebook."""
        settings = Settings(azure_client_id="test-id", notebook_name="The Process")
        assert settings.notebook_name == "The Process"
