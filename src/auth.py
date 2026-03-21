"""Authentification Azure AD via MSAL device code flow."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

import click
import msal

from src.config import get_settings

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Levée quand l'authentification Azure AD échoue."""

    pass


def authenticate() -> tuple[str, msal.PublicClientApplication]:
    """Authentifie l'utilisateur avec cache MSAL persistant.

    Premier appel : device code flow, cache sauvegardé sur disque.
    Appels suivants : acquire_token_silent depuis le cache (~24h).

    Returns:
        Tuple (access_token, app) pour refresh ultérieur.

    Raises:
        AuthenticationError: Si l'authentification échoue.
        ValueError: Si le client_id est vide.
    """
    settings = get_settings()

    if not settings.azure_client_id:
        raise ValueError("azure_client_id ne peut pas être vide")

    # Charger le cache disque
    cache = msal.SerializableTokenCache()
    cache_path = settings.cache_dir / "msal_cache.bin"
    if cache_path.exists():
        try:
            cache.deserialize(cache_path.read_text())  # pyright: ignore[reportUnknownMemberType]
        except Exception:
            logger.warning("Cache MSAL corrompu, re-authentification")

    authority = f"https://login.microsoftonline.com/{settings.azure_tenant_id}"
    app: msal.PublicClientApplication = msal.PublicClientApplication(
        settings.azure_client_id,
        authority=authority,
        token_cache=cache,
    )

    # Essayer silent d'abord
    accounts = app.get_accounts()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if accounts:
        result = cast(
            "dict[str, Any]",
            app.acquire_token_silent(scopes=["Notes.Read"], account=accounts[0]),  # pyright: ignore[reportUnknownMemberType]
        )
        if result and "access_token" in result:
            click.echo("Auth: token refreshed from cache")
            _save_cache(cache, cache_path)
            return str(result["access_token"]), app

    # Fallback device code flow
    flow = cast("dict[str, Any]", app.initiate_device_flow(scopes=["Notes.Read"]))  # pyright: ignore[reportUnknownMemberType]

    if "error" in flow:
        raise AuthenticationError(
            f"Device flow init failed: {flow['error']} — {flow.get('error_description', '')}"
        )

    if "message" in flow:
        click.echo(flow["message"])

    result = cast("dict[str, Any]", app.acquire_token_by_device_flow(flow))  # pyright: ignore[reportUnknownMemberType]

    if "error" in result:
        error_code = str(result.get("error", "unknown"))
        error_desc = str(result.get("error_description", ""))
        msg = f"Authentication failed: {error_code} — {error_desc}"
        logger.error(msg)
        raise AuthenticationError(msg)

    _save_cache(cache, cache_path)
    return str(result["access_token"]), app


def _save_cache(cache: msal.SerializableTokenCache, path: Path) -> None:
    """Sauvegarde atomique du cache MSAL sur disque.

    Args:
        cache: Instance SerializableTokenCache à persister.
        path: Chemin du fichier cache.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cache.serialize())  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    path.chmod(0o600)


def refresh_token(app: msal.PublicClientApplication) -> str:
    """Refresh le token silencieusement via le cache MSAL.

    Args:
        app: Instance PublicClientApplication avec un token en cache.

    Returns:
        Nouveau access token.

    Raises:
        AuthenticationError: Si le refresh silencieux échoue.
    """
    accounts = app.get_accounts()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if accounts:
        result = app.acquire_token_silent(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            scopes=["Notes.Read"],
            account=accounts[0],  # pyright: ignore[reportUnknownArgumentType]
        )
        if result and "access_token" in result:
            return str(result["access_token"])  # pyright: ignore[reportUnknownArgumentType]
    raise AuthenticationError("Token refresh failed — re-authentication required")
