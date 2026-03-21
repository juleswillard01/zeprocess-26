"""Tests pour le client Microsoft Graph API."""

from __future__ import annotations

import asyncio
import unittest.mock as mock
from typing import Any

import httpx
import pytest

from src.graph import GraphAPIError, GraphClient, Notebook, Page, Section

BASE = "https://graph.microsoft.com/v1.0/me/onenote"


def _make_transport(routes: dict[str, Any]) -> httpx.MockTransport:
    """Crée un MockTransport qui route par URL exacte.

    Args:
        routes: Dict URL → Response ou list[Response] pour side_effect.
    """
    call_counts: dict[str, int] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url not in routes:
            return httpx.Response(404, json={"error": f"No mock for {url}"})

        route_val = routes[url]
        if isinstance(route_val, list):
            idx = call_counts.get(url, 0)
            call_counts[url] = idx + 1
            return route_val[idx]
        return route_val

    return httpx.MockTransport(handler)


def _json_response(data: Any, status: int = 200) -> httpx.Response:
    """Crée une httpx.Response JSON."""
    return httpx.Response(status, json=data)


def _text_response(text: str, status: int = 200) -> httpx.Response:
    """Crée une httpx.Response texte."""
    return httpx.Response(status, text=text)


def _rate_limit_response(retry_after: str = "0") -> httpx.Response:
    """Crée une réponse 429 rate limit."""
    return httpx.Response(429, headers={"Retry-After": retry_after})


def _make_client(routes: dict[str, Any], token: str = "test-token") -> GraphClient:
    """Crée un GraphClient avec transport mocké."""
    transport = _make_transport(routes)
    http_client = httpx.AsyncClient(transport=transport)
    return GraphClient(access_token=token, http_client=http_client)


class TestGraphModels:
    """Tests pour les dataclasses du module graph."""

    def test_notebook_has_required_fields(self) -> None:
        """Un Notebook doit avoir un id et un display_name."""
        nb = Notebook(id="nb-1", display_name="Mon Notebook")
        assert nb.id == "nb-1"
        assert nb.display_name == "Mon Notebook"

    def test_section_has_notebook_reference(self) -> None:
        """Une Section doit référencer son notebook parent."""
        section = Section(id="sec-1", display_name="Section A", notebook_id="nb-1")
        assert section.notebook_id == "nb-1"

    def test_page_has_default_order_zero(self) -> None:
        """Une Page doit avoir un ordre par défaut de 0."""
        page = Page(id="p-1", title="Page 1", section_id="sec-1", created_date_time="2025-01-01")
        assert page.order == 0


class TestGraphClient:
    """Tests pour le client Graph API."""

    def test_client_stores_token(self) -> None:
        """Le client doit stocker le token fourni."""
        client = GraphClient(access_token="test-token-123")
        assert client._token == "test-token-123"

    @pytest.mark.asyncio
    async def test_list_notebooks_returns_notebooks(self) -> None:
        """list_notebooks doit retourner les notebooks parsés depuis l'API."""
        client = _make_client(
            {
                f"{BASE}/notebooks": _json_response(
                    {
                        "value": [
                            {"id": "nb-1", "displayName": "Notebook 1"},
                            {"id": "nb-2", "displayName": "Notebook 2"},
                        ]
                    }
                ),
            }
        )

        notebooks = await client.list_notebooks()

        assert len(notebooks) == 2
        assert notebooks[0].id == "nb-1"
        assert notebooks[0].display_name == "Notebook 1"
        assert notebooks[1].id == "nb-2"
        assert notebooks[1].display_name == "Notebook 2"

    @pytest.mark.asyncio
    async def test_list_notebooks_handles_pagination(self) -> None:
        """list_notebooks doit gérer la pagination via @odata.nextLink."""
        next_url = f"{BASE}/notebooks?$skip=1"
        client = _make_client(
            {
                f"{BASE}/notebooks": _json_response(
                    {
                        "value": [{"id": "nb-1", "displayName": "Notebook 1"}],
                        "@odata.nextLink": next_url,
                    }
                ),
                next_url: _json_response(
                    {
                        "value": [{"id": "nb-2", "displayName": "Notebook 2"}],
                    }
                ),
            }
        )

        notebooks = await client.list_notebooks()

        assert len(notebooks) == 2
        assert notebooks[0].display_name == "Notebook 1"
        assert notebooks[1].display_name == "Notebook 2"

    @pytest.mark.asyncio
    async def test_list_sections_returns_sections(self) -> None:
        """list_sections doit retourner les sections d'un notebook."""
        client = _make_client(
            {
                f"{BASE}/notebooks/nb-1/sections": _json_response(
                    {
                        "value": [
                            {"id": "sec-1", "displayName": "Section A"},
                            {"id": "sec-2", "displayName": "Section B"},
                        ]
                    }
                ),
                f"{BASE}/notebooks/nb-1/sectionGroups": _json_response({"value": []}),
            }
        )

        sections = await client.list_sections("nb-1")

        assert len(sections) == 2
        assert sections[0].id == "sec-1"
        assert sections[0].display_name == "Section A"
        assert sections[0].notebook_id == "nb-1"
        assert sections[1].id == "sec-2"

    @pytest.mark.asyncio
    async def test_list_sections_handles_nested_section_groups(self) -> None:
        """list_sections doit récursivement récupérer les sections des groupes."""
        client = _make_client(
            {
                f"{BASE}/notebooks/nb-1/sections": _json_response(
                    {"value": [{"id": "sec-1", "displayName": "Direct Section"}]}
                ),
                f"{BASE}/notebooks/nb-1/sectionGroups": _json_response(
                    {"value": [{"id": "sg-1", "displayName": "Section Group 1"}]}
                ),
                f"{BASE}/sectionGroups/sg-1/sections": _json_response(
                    {"value": [{"id": "sec-2", "displayName": "Nested Section"}]}
                ),
                f"{BASE}/sectionGroups/sg-1/sectionGroups": _json_response({"value": []}),
            }
        )

        sections = await client.list_sections("nb-1")

        assert len(sections) == 2
        assert any(s.id == "sec-1" for s in sections)
        assert any(s.id == "sec-2" for s in sections)
        assert all(s.notebook_id == "nb-1" for s in sections)

    @pytest.mark.asyncio
    async def test_list_pages_returns_ordered_pages(self) -> None:
        """list_pages doit retourner les pages avec ordre attribué."""
        client = _make_client(
            {
                f"{BASE}/sections/sec-1/pages": _json_response(
                    {
                        "value": [
                            {
                                "id": "p-1",
                                "title": "Page 1",
                                "createdDateTime": "2025-01-01T10:00:00Z",
                            },
                            {
                                "id": "p-2",
                                "title": "Page 2",
                                "createdDateTime": "2025-01-02T10:00:00Z",
                            },
                            {
                                "id": "p-3",
                                "title": "Page 3",
                                "createdDateTime": "2025-01-03T10:00:00Z",
                            },
                        ]
                    }
                ),
            }
        )

        pages = await client.list_pages("sec-1")

        assert len(pages) == 3
        assert pages[0].id == "p-1"
        assert pages[0].order == 0
        assert pages[1].order == 1
        assert pages[2].order == 2
        assert all(p.section_id == "sec-1" for p in pages)

    @pytest.mark.asyncio
    async def test_get_page_content_returns_html(self) -> None:
        """get_page_content doit retourner le contenu HTML d'une page."""
        html_content = "<html><body><p>Test content</p></body></html>"
        client = _make_client(
            {
                f"{BASE}/pages/p-1/content": _text_response(html_content),
            }
        )

        content = await client.get_page_content("p-1")

        assert content == html_content
        assert "<p>Test content</p>" in content

    @pytest.mark.asyncio
    async def test_client_handles_429_with_retry(self) -> None:
        """Le client doit retry après une réponse 429 (rate limit)."""
        client = _make_client(
            {
                f"{BASE}/notebooks": [
                    _rate_limit_response("0"),
                    _json_response({"value": [{"id": "nb-1", "displayName": "Notebook 1"}]}),
                ],
            }
        )

        notebooks = await client.list_notebooks()

        assert len(notebooks) == 1
        assert notebooks[0].id == "nb-1"

    @pytest.mark.asyncio
    async def test_client_raises_on_api_error(self) -> None:
        """Le client doit lever GraphAPIError sur une réponse 500."""
        client = _make_client(
            {
                f"{BASE}/notebooks": httpx.Response(
                    500, json={"error": {"message": "Server error"}}
                ),
            }
        )

        with pytest.raises(GraphAPIError):
            await client.list_notebooks()

    @pytest.mark.asyncio
    async def test_client_sends_authorization_header(self) -> None:
        """Le client doit envoyer le Bearer token dans Authorization."""
        captured_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, json={"value": []})

        transport = httpx.MockTransport(handler)
        http_client = httpx.AsyncClient(transport=transport)
        client = GraphClient(access_token="test-secret-token", http_client=http_client)

        await client.list_notebooks()

        assert "authorization" in captured_headers
        assert captured_headers["authorization"] == "Bearer test-secret-token"

    @pytest.mark.asyncio
    async def test_close_closes_owned_client(self) -> None:
        """close() doit fermer le client créé internement."""
        client = GraphClient(access_token="token")
        await client._get_client()
        assert client._client is not None
        await client.close()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_close_does_not_close_injected_client(self) -> None:
        """close() ne doit pas fermer un client injecté."""
        http_client = httpx.AsyncClient()
        client = GraphClient(access_token="token", http_client=http_client)
        await client.close()
        assert client._client is not None
        await http_client.aclose()

    @pytest.mark.asyncio
    async def test_fetch_paginated_raises_on_untrusted_nextlink(self) -> None:
        """_fetch_paginated doit lever GraphAPIError si nextLink n'est pas graph.microsoft.com."""
        malicious_next = "https://evil.example.com/steal?token=abc"
        client = _make_client(
            {
                f"{BASE}/notebooks": _json_response(
                    {
                        "value": [{"id": "nb-1", "displayName": "Notebook 1"}],
                        "@odata.nextLink": malicious_next,
                    }
                ),
            }
        )

        with pytest.raises(GraphAPIError, match="Untrusted nextLink URL"):
            await client.list_notebooks()

    @pytest.mark.asyncio
    async def test_request_caps_retry_after_at_60s(self) -> None:
        """_request doit plafonner Retry-After à 60s même si l'API renvoie une valeur supérieure."""
        slept: list[float] = []
        original_sleep = asyncio.sleep

        async def mock_sleep(delay: float) -> None:
            slept.append(delay)
            await original_sleep(0)

        client = _make_client(
            {
                f"{BASE}/notebooks": [
                    httpx.Response(429, headers={"Retry-After": "9999"}),
                    _json_response({"value": [{"id": "nb-1", "displayName": "N1"}]}),
                ],
            }
        )

        with mock.patch("asyncio.sleep", side_effect=mock_sleep):
            notebooks = await client.list_notebooks()

        assert len(notebooks) == 1
        assert slept == [60.0]

    @pytest.mark.asyncio
    async def test_request_raises_after_max_retries_exhausted(self) -> None:
        """_request doit lever GraphAPIError après 5 réponses 429 consécutives."""

        client = _make_client(
            {
                f"{BASE}/notebooks": [
                    httpx.Response(429, headers={"Retry-After": "0"}),
                    httpx.Response(429, headers={"Retry-After": "0"}),
                    httpx.Response(429, headers={"Retry-After": "0"}),
                    httpx.Response(429, headers={"Retry-After": "0"}),
                    httpx.Response(429, headers={"Retry-After": "0"}),
                ],
            }
        )

        with (
            mock.patch("asyncio.sleep", return_value=None),
            pytest.raises(GraphAPIError, match="Rate limit exceeded after 5 retries"),
        ):
            await client.list_notebooks()

    def test_update_token_changes_stored_token(self) -> None:
        """update_token doit remplacer le token stocké."""
        client = GraphClient(access_token="old-token")
        client.update_token("new-token")
        assert client._token == "new-token"


class TestDownloadResource:
    """Tests pour le téléchargement de ressources binaires."""

    @pytest.mark.asyncio
    async def test_download_resource_returns_bytes(self) -> None:
        """download_resource doit retourner les bytes de la ressource."""
        resource_url = "https://graph.microsoft.com/v1.0/me/onenote/resources/res-1/$value"
        image_bytes = b"\x89PNG\r\nfake image data"
        client = _make_client(
            {
                resource_url: httpx.Response(200, content=image_bytes),
            }
        )

        result = await client.download_resource(resource_url)

        assert result == image_bytes

    @pytest.mark.asyncio
    async def test_download_resource_sends_auth_header(self) -> None:
        """download_resource doit envoyer le Bearer token dans Authorization."""
        resource_url = "https://graph.microsoft.com/v1.0/me/onenote/resources/res-2/$value"
        captured_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, content=b"fake bytes")

        transport = httpx.MockTransport(handler)
        http_client = httpx.AsyncClient(transport=transport)
        client = GraphClient(access_token="secret-bearer-token", http_client=http_client)

        await client.download_resource(resource_url)

        assert "authorization" in captured_headers
        assert captured_headers["authorization"] == "Bearer secret-bearer-token"

    @pytest.mark.asyncio
    async def test_download_resource_raises_on_error(self) -> None:
        """download_resource doit lever GraphAPIError sur une réponse 401."""
        resource_url = "https://graph.microsoft.com/v1.0/me/onenote/resources/res-3/$value"
        client = _make_client(
            {
                resource_url: httpx.Response(401, json={"error": "Unauthorized"}),
            }
        )

        with pytest.raises(GraphAPIError):
            await client.download_resource(resource_url)
