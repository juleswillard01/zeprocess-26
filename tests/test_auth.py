"""Tests pour l'authentification Azure AD via MSAL device code flow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.auth import AuthenticationError, authenticate
from src.config import Settings


class TestAuthenticationError:
    """Tests pour l'exception AuthenticationError."""

    def test_authentication_error_is_exception(self) -> None:
        """AuthenticationError doit hériter de Exception."""
        assert issubclass(AuthenticationError, Exception)

    def test_authentication_error_can_be_raised_with_message(self) -> None:
        """AuthenticationError doit pouvoir être levée avec un message."""
        with pytest.raises(AuthenticationError, match="Auth failed"):
            raise AuthenticationError("Auth failed")

    def test_authentication_error_message_is_accessible(self) -> None:
        """Le message d'AuthenticationError doit être accessible."""
        error = AuthenticationError("Test message")
        assert str(error) == "Test message"


class TestAuthenticate:
    """Tests pour la fonction authenticate()."""

    def test_authenticate_success_returns_token(self) -> None:
        """authenticate() doit retourner un access token valide en cas de succès."""
        mock_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        mock_app = MagicMock()
        mock_flow = {"device_code": "test-code"}
        mock_result = {"access_token": mock_token}

        mock_app.initiate_device_flow.return_value = mock_flow
        mock_app.acquire_token_by_device_flow.return_value = mock_result

        with (
            patch("src.auth.msal.PublicClientApplication", return_value=mock_app),
            patch("src.auth.get_settings") as mock_settings,
        ):
            mock_settings.return_value = Settings(
                azure_client_id="test-client-id",
                azure_tenant_id="common",
            )
            result = authenticate()

        assert result == mock_token
        assert isinstance(result, str)

    def test_authenticate_displays_device_code_message(self) -> None:
        """authenticate() doit afficher le message du device code à l'utilisateur."""
        mock_message = (
            "To sign in, use a web browser to open the page https://example.com "
            "and enter code ABC123"
        )
        mock_app = MagicMock()
        mock_flow = {"device_code": "test-code", "message": mock_message}
        mock_result = {"access_token": "test-token"}

        mock_app.initiate_device_flow.return_value = mock_flow
        mock_app.acquire_token_by_device_flow.return_value = mock_result

        with (
            patch("src.auth.msal.PublicClientApplication", return_value=mock_app),
            patch("src.auth.get_settings") as mock_settings,
            patch("src.auth.click.echo") as mock_echo,
        ):
            mock_settings.return_value = Settings(
                azure_client_id="test-client-id",
                azure_tenant_id="common",
            )
            authenticate()

            mock_echo.assert_called_once_with(mock_message)

    def test_authenticate_device_flow_init_error_raises(self) -> None:
        """authenticate() doit lever AuthenticationError si device flow init échoue."""
        mock_app = MagicMock()
        mock_app.initiate_device_flow.return_value = {
            "error": "bad_request",
            "error_description": "Invalid scope",
        }

        with (
            patch("src.auth.msal.PublicClientApplication", return_value=mock_app),
            patch("src.auth.get_settings") as mock_settings,
        ):
            mock_settings.return_value = Settings(
                azure_client_id="test",
                azure_tenant_id="common",
            )
            with pytest.raises(AuthenticationError, match="Device flow init failed"):
                authenticate()

    def test_authenticate_error_raises_authentication_error(self) -> None:
        """authenticate() doit lever AuthenticationError si l'API retourne une erreur."""
        mock_app = MagicMock()
        mock_flow = {"device_code": "test-code"}
        mock_result = {
            "error": "authorization_pending",
            "error_description": "User denied access",
        }

        mock_app.initiate_device_flow.return_value = mock_flow
        mock_app.acquire_token_by_device_flow.return_value = mock_result

        with (
            patch("src.auth.msal.PublicClientApplication", return_value=mock_app),
            patch("src.auth.get_settings") as mock_settings,
        ):
            mock_settings.return_value = Settings(
                azure_client_id="test-client-id",
                azure_tenant_id="common",
            )
            with pytest.raises(AuthenticationError):
                authenticate()

    def test_authenticate_uses_correct_scopes(self) -> None:
        """authenticate() doit utiliser la permission Notes.Read uniquement."""
        mock_app = MagicMock()
        mock_flow = {"device_code": "test-code"}
        mock_result = {"access_token": "test-token"}

        mock_app.initiate_device_flow.return_value = mock_flow
        mock_app.acquire_token_by_device_flow.return_value = mock_result

        with (
            patch("src.auth.msal.PublicClientApplication", return_value=mock_app),
            patch("src.auth.get_settings") as mock_settings,
        ):
            mock_settings.return_value = Settings(
                azure_client_id="test-client-id",
                azure_tenant_id="common",
            )
            authenticate()

        mock_app.initiate_device_flow.assert_called_once()
        call_kwargs = mock_app.initiate_device_flow.call_args[1]
        assert "scopes" in call_kwargs
        scopes = call_kwargs["scopes"]
        assert "Notes.Read" in scopes or (isinstance(scopes, list) and "Notes.Read" in scopes)

    def test_authenticate_uses_settings_client_id(self) -> None:
        """authenticate() doit utiliser le client_id depuis la configuration."""
        mock_client_id = "test-client-id-12345"
        mock_app = MagicMock()
        mock_flow = {"device_code": "test-code"}
        mock_result = {"access_token": "test-token"}

        mock_app.initiate_device_flow.return_value = mock_flow
        mock_app.acquire_token_by_device_flow.return_value = mock_result

        with (
            patch("src.auth.msal.PublicClientApplication") as mock_msal,
            patch("src.auth.get_settings") as mock_settings,
        ):
            mock_msal.return_value = mock_app
            mock_settings.return_value = Settings(
                azure_client_id=mock_client_id,
                azure_tenant_id="common",
            )
            authenticate()

            mock_msal.assert_called_once()
            call_args = mock_msal.call_args
            assert (
                call_args[0][0] == mock_client_id or call_args[1].get("client_id") == mock_client_id
            )

    def test_authenticate_uses_correct_authority_url(self) -> None:
        """authenticate() doit construire l'authority URL avec le tenant depuis la configuration."""
        mock_app = MagicMock()
        mock_flow = {"device_code": "test-code"}
        mock_result = {"access_token": "test-token"}

        mock_app.initiate_device_flow.return_value = mock_flow
        mock_app.acquire_token_by_device_flow.return_value = mock_result

        with (
            patch("src.auth.msal.PublicClientApplication") as mock_msal,
            patch("src.auth.get_settings") as mock_settings,
        ):
            mock_msal.return_value = mock_app
            mock_settings.return_value = Settings(
                azure_client_id="test-client-id",
                azure_tenant_id="common",
            )
            authenticate()

            call_kwargs = mock_msal.call_args[1]
            authority = call_kwargs.get("authority", "")
            assert "https://login.microsoftonline.com/" in authority
            assert "common" in authority

    def test_authenticate_supports_tenant_common(self) -> None:
        """authenticate() doit supporter le tenant 'common' pour les comptes personnels."""
        mock_app = MagicMock()
        mock_flow = {"device_code": "test-code"}
        mock_result = {"access_token": "test-token"}

        mock_app.initiate_device_flow.return_value = mock_flow
        mock_app.acquire_token_by_device_flow.return_value = mock_result

        with (
            patch("src.auth.msal.PublicClientApplication") as mock_msal,
            patch("src.auth.get_settings") as mock_settings,
        ):
            mock_msal.return_value = mock_app
            mock_settings.return_value = Settings(
                azure_client_id="test-client-id",
                azure_tenant_id="common",
            )
            result = authenticate()

        assert result == "test-token"
        call_kwargs = mock_msal.call_args[1]
        authority = call_kwargs.get("authority", "")
        assert "common" in authority

    def test_authenticate_supports_custom_tenant(self) -> None:
        """authenticate() doit supporter les tenant IDs personnalisés."""
        custom_tenant = "00000000-0000-0000-0000-000000000001"
        mock_app = MagicMock()
        mock_flow = {"device_code": "test-code"}
        mock_result = {"access_token": "test-token"}

        mock_app.initiate_device_flow.return_value = mock_flow
        mock_app.acquire_token_by_device_flow.return_value = mock_result

        with (
            patch("src.auth.msal.PublicClientApplication") as mock_msal,
            patch("src.auth.get_settings") as mock_settings,
        ):
            mock_msal.return_value = mock_app
            mock_settings.return_value = Settings(
                azure_client_id="test-client-id",
                azure_tenant_id=custom_tenant,
            )
            authenticate()

            call_kwargs = mock_msal.call_args[1]
            authority = call_kwargs.get("authority", "")
            assert custom_tenant in authority

    def test_authenticate_error_includes_error_details(self) -> None:
        """AuthenticationError levée doit inclure les détails de l'erreur."""
        mock_app = MagicMock()
        mock_flow = {"device_code": "test-code"}
        error_msg = "User cancelled authentication"
        mock_result = {"error": "user_cancelled", "error_description": error_msg}

        mock_app.initiate_device_flow.return_value = mock_flow
        mock_app.acquire_token_by_device_flow.return_value = mock_result

        with (
            patch("src.auth.msal.PublicClientApplication", return_value=mock_app),
            patch("src.auth.get_settings") as mock_settings,
        ):
            mock_settings.return_value = Settings(
                azure_client_id="test-client-id",
                azure_tenant_id="common",
            )
            with pytest.raises(AuthenticationError) as exc_info:
                authenticate()

            error_message = str(exc_info.value)
            assert len(error_message) > 0

    def test_authenticate_calls_acquire_token_with_flow(self) -> None:
        """authenticate() doit appeler acquire_token_by_device_flow avec le flow retourné."""
        mock_app = MagicMock()
        mock_flow = {"device_code": "test-code", "message": "test-message"}
        mock_result = {"access_token": "test-token"}

        mock_app.initiate_device_flow.return_value = mock_flow
        mock_app.acquire_token_by_device_flow.return_value = mock_result

        with (
            patch("src.auth.msal.PublicClientApplication", return_value=mock_app),
            patch("src.auth.get_settings") as mock_settings,
        ):
            mock_settings.return_value = Settings(
                azure_client_id="test-client-id",
                azure_tenant_id="common",
            )
            authenticate()

        mock_app.acquire_token_by_device_flow.assert_called_once()
        call_args = mock_app.acquire_token_by_device_flow.call_args[0]
        assert call_args[0] == mock_flow or (call_args and call_args[0] == mock_flow)

    def test_authenticate_with_missing_client_id_raises_error(self) -> None:
        """authenticate() doit lever une erreur si le client_id est vide."""
        with patch("src.auth.get_settings") as mock_settings:
            mock_settings.return_value = Settings(
                azure_client_id="",
                azure_tenant_id="common",
            )
            with pytest.raises((ValueError, AuthenticationError)):
                authenticate()
