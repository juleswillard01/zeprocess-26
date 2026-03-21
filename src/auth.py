"""Authentification Azure AD via MSAL device code flow."""

from __future__ import annotations

import logging
from typing import Any, cast

import click
import msal

from src.config import get_settings

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Levée quand l'authentification Azure AD échoue."""

    pass


def authenticate() -> str:
    """Authentifie l'utilisateur et retourne un access token.

    Utilise le device code flow MSAL pour obtenir un token
    sans nécessiter de client_secret.

    Returns:
        Access token valide pour Microsoft Graph API.

    Raises:
        AuthenticationError: Si l'authentification échoue.
        ValueError: Si le client_id est vide.
    """
    settings = get_settings()

    if not settings.azure_client_id:
        raise ValueError("azure_client_id ne peut pas être vide")

    authority = f"https://login.microsoftonline.com/{settings.azure_tenant_id}"
    app: msal.PublicClientApplication = msal.PublicClientApplication(
        settings.azure_client_id,
        authority=authority,
    )

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

    return str(result["access_token"])
