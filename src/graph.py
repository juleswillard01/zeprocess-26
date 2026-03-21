"""Client Microsoft Graph API pour OneNote."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import click
import httpx

logger = logging.getLogger(__name__)

_TRUSTED_NEXTLINK_PREFIX = "https://graph.microsoft.com/"
_MAX_RETRIES = 5
_MAX_RETRY_AFTER = 60.0


class GraphAPIError(Exception):
    """Exception levée quand l'appel à l'API Graph échoue."""

    pass


@dataclass
class Notebook:
    """Représente un notebook OneNote."""

    id: str
    display_name: str


@dataclass
class Section:
    """Représente une section OneNote."""

    id: str
    display_name: str
    notebook_id: str


@dataclass
class Page:
    """Représente une page OneNote."""

    id: str
    title: str
    section_id: str
    created_date_time: str
    order: int = 0


class GraphClient:
    """Client pour l'API Microsoft Graph OneNote."""

    BASE_URL = "https://graph.microsoft.com/v1.0/me/onenote"

    def __init__(self, access_token: str, http_client: httpx.AsyncClient | None = None) -> None:
        """Initialise le client avec un access token.

        Args:
            access_token: Token Bearer pour l'API Graph.
            http_client: Client httpx optionnel (injection pour tests).
        """
        self._token = access_token
        self._client: httpx.AsyncClient | None = http_client
        self._owns_client = http_client is None

    async def _get_client(self) -> httpx.AsyncClient:
        """Obtient ou crée le client HTTP asynchrone."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0))
        return self._client

    async def close(self) -> None:
        """Ferme proprement le client HTTP si le client est géré internement."""
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    def update_token(self, new_token: str) -> None:
        """Met à jour le token d'authentification.

        Args:
            new_token: Nouveau access token Bearer.
        """
        self._token = new_token

    async def _request(self, url: str) -> httpx.Response:
        """Exécute une requête GET avec retry automatique sur 429.

        Utilise une boucle itérative (max 5 tentatives) pour éviter la récursion.
        Le délai Retry-After est plafonné à 60 secondes.

        Args:
            url: URL complète à appeler.

        Returns:
            Réponse httpx brute (JSON ou texte selon besoin de l'appelant).

        Raises:
            GraphAPIError: Si l'appel échoue ou si le rate limit est dépassé.
        """
        headers = {"Authorization": f"Bearer {self._token}"}
        client = await self._get_client()

        for attempt in range(_MAX_RETRIES):
            response = await client.get(url, headers=headers)

            if response.status_code == 429:
                raw = response.headers.get("Retry-After", "1")
                try:
                    retry_after = min(float(raw), _MAX_RETRY_AFTER)
                except ValueError:
                    retry_after = 1.0
                logger.warning(
                    "Rate limited (attempt %d/%d), sleeping %.1fs",
                    attempt + 1,
                    _MAX_RETRIES,
                    retry_after,
                )
                click.echo(f"  Rate limited, waiting {retry_after:.0f}s...")
                await asyncio.sleep(retry_after)
                continue

            if response.status_code >= 400:
                raise GraphAPIError(f"API error {response.status_code}: {response.text[:200]}")

            return response

        raise GraphAPIError(f"Rate limit exceeded after {_MAX_RETRIES} retries for {url}")

    async def _fetch_paginated(self, url: str) -> list[dict[str, Any]]:
        """Récupère tous les éléments paginés depuis une URL.

        Args:
            url: URL de départ.

        Returns:
            Liste complète des éléments.

        Raises:
            GraphAPIError: Si l'appel API échoue ou si nextLink est non fiable.
        """
        items: list[dict[str, Any]] = []
        current_url: str | None = url

        while current_url:
            response = await self._request(current_url)
            response_data: dict[str, Any] = response.json()
            items.extend(response_data.get("value", []))

            next_link = response_data.get("@odata.nextLink")
            if next_link and not next_link.startswith(_TRUSTED_NEXTLINK_PREFIX):
                raise GraphAPIError(f"Untrusted nextLink URL: {next_link}")
            current_url = next_link

        return items

    async def list_notebooks(self) -> list[Notebook]:
        """Liste tous les notebooks de l'utilisateur.

        Returns:
            Liste de notebooks.

        Raises:
            GraphAPIError: Si l'appel API échoue.
        """
        click.echo("Fetching notebooks...")
        url = f"{self.BASE_URL}/notebooks"
        items = await self._fetch_paginated(url)
        notebooks = [Notebook(id=item["id"], display_name=item["displayName"]) for item in items]
        click.echo(f"  Found {len(notebooks)} notebook(s)")
        return notebooks

    async def list_sections(self, notebook_id: str) -> list[Section]:
        """Liste les sections d'un notebook.

        Args:
            notebook_id: ID du notebook.

        Returns:
            Liste de sections.
        """
        click.echo(f"  Fetching sections for notebook {notebook_id[:8]}...")
        sections: list[Section] = []

        url = f"{self.BASE_URL}/notebooks/{notebook_id}/sections"
        items = await self._fetch_paginated(url)
        sections.extend(
            [
                Section(id=item["id"], display_name=item["displayName"], notebook_id=notebook_id)
                for item in items
            ]
        )

        sg_url = f"{self.BASE_URL}/notebooks/{notebook_id}/sectionGroups"
        sg_items = await self._fetch_paginated(sg_url)
        for sg in sg_items:
            nested_sections = await self._list_sections_in_group(str(sg["id"]), notebook_id)
            sections.extend(nested_sections)

        click.echo(f"    Found {len(sections)} section(s)")
        return sections

    async def _list_sections_in_group(self, group_id: str, notebook_id: str) -> list[Section]:
        """Récursivement récupère les sections d'un groupe de sections.

        Args:
            group_id: ID du groupe de sections.
            notebook_id: ID du notebook parent (pour référence).

        Returns:
            Liste de sections du groupe.
        """
        sections: list[Section] = []

        url = f"{self.BASE_URL}/sectionGroups/{group_id}/sections"
        items = await self._fetch_paginated(url)
        sections.extend(
            [
                Section(id=item["id"], display_name=item["displayName"], notebook_id=notebook_id)
                for item in items
            ]
        )

        sg_url = f"{self.BASE_URL}/sectionGroups/{group_id}/sectionGroups"
        sg_items = await self._fetch_paginated(sg_url)
        for sg in sg_items:
            nested = await self._list_sections_in_group(str(sg["id"]), notebook_id)
            sections.extend(nested)

        return sections

    async def list_pages(self, section_id: str) -> list[Page]:
        """Liste les pages d'une section.

        Args:
            section_id: ID de la section.

        Returns:
            Liste de pages.
        """
        click.echo(f"    Fetching pages for section {section_id[:8]}...")
        url = f"{self.BASE_URL}/sections/{section_id}/pages"
        items = await self._fetch_paginated(url)

        pages: list[Page] = []
        for order, item in enumerate(items):
            page = Page(
                id=str(item["id"]),
                title=str(item["title"]),
                section_id=section_id,
                created_date_time=str(item["createdDateTime"]),
                order=order,
            )
            pages.append(page)

        click.echo(f"      Found {len(pages)} page(s)")
        return pages

    async def get_page_content(self, page_id: str) -> str:
        """Récupère le contenu HTML d'une page.

        Args:
            page_id: ID de la page.

        Returns:
            Contenu HTML de la page.

        Raises:
            GraphAPIError: Si l'appel API échoue.
        """
        logger.info("Fetching content for page %s", page_id[:8])
        url = f"{self.BASE_URL}/pages/{page_id}/content"
        response = await self._request(url)
        return response.text

    async def download_resource(self, url: str) -> bytes:
        """Télécharge une ressource binaire via l'API Graph (ex: image embarquée).

        Args:
            url: URL complète de la ressource Graph (ex: .../resources/{id}/$value).

        Returns:
            Bytes bruts de la ressource.

        Raises:
            GraphAPIError: Si l'appel API échoue.
        """
        logger.info("Downloading resource %s", url[:60])
        response = await self._request(url)
        return response.content
