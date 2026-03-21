"""Mapping de la hiérarchie OneNote en arbre avec comptage de pages."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from io import StringIO
from typing import TYPE_CHECKING, Any

import click
from rich.console import Console
from rich.tree import Tree

from src.config import get_settings

if TYPE_CHECKING:
    from pathlib import Path

    from src.graph import GraphClient

logger = logging.getLogger(__name__)


@dataclass
class HierarchyNode:
    """Nœud dans l'arbre de hiérarchie OneNote."""

    name: str
    node_type: str  # "notebook", "section_group", "section"
    id: str
    page_count: int = 0
    page_ids: list[str] = field(default_factory=lambda: [])
    page_titles: dict[str, str] = field(default_factory=lambda: {})
    children: list[HierarchyNode] = field(default_factory=lambda: [])

    @property
    def total_pages(self) -> int:
        """Nombre total de pages incluant les enfants."""
        return self.page_count + sum(c.total_pages for c in self.children)


def _load_cache(cache_file: Path, ttl: int) -> list[HierarchyNode] | None:
    """Lit le cache si valide et non corrompu, sinon retourne None.

    Args:
        cache_file: Chemin vers le fichier de cache JSON.
        ttl: Durée de vie maximale du cache en secondes.

    Returns:
        Liste de nœuds désérialisés ou None si le cache est absent/expiré/corrompu.
    """
    if not cache_file.exists():
        return None
    cache_age = time.time() - cache_file.stat().st_mtime
    if cache_age >= ttl:
        return None
    try:
        with cache_file.open() as f:
            cached_data = json.load(f)
        nodes = _deserialize_nodes(cached_data)
        click.echo("Using cached hierarchy (use --no-cache to refresh)")
        return nodes
    except (json.JSONDecodeError, KeyError):
        logger.warning("Cache file corrupt, refetching from API")
        return None


def _save_cache(cache_file: Path, nodes: list[HierarchyNode]) -> None:
    """Écrit atomiquement la hiérarchie en cache JSON.

    Utilise write-to-tmp + rename pour éviter les fichiers partiels.

    Args:
        cache_file: Chemin cible du cache.
        nodes: Nœuds à sérialiser.
    """
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = cache_file.with_suffix(".tmp")
    with tmp_file.open("w") as f:
        json.dump(_serialize_nodes(nodes), f)
    tmp_file.rename(cache_file)
    click.echo("Hierarchy cached.")


async def build_tree(client: GraphClient, no_cache: bool = False) -> list[HierarchyNode]:
    """Construit l'arbre de hiérarchie complet depuis l'API Graph.

    Args:
        client: Client GraphClient pour accéder à l'API.
        no_cache: Si True, ignore le cache et refait les appels API.

    Returns:
        Liste de nœuds racine (notebooks).

    Raises:
        GraphAPIError: Si un appel API échoue.
    """
    settings = get_settings()
    cache_file = settings.cache_dir / "hierarchy.json"

    click.echo("Building OneNote hierarchy...")

    if not no_cache:
        cached = _load_cache(cache_file, settings.cache_ttl_seconds)
        if cached is not None:
            return cached

    notebooks = await client.list_notebooks()
    click.echo(f"Found {len(notebooks)} notebook(s)")

    # Filter by notebook name if configured
    if settings.notebook_name:
        target = settings.notebook_name.lower()
        filtered = [nb for nb in notebooks if target in nb.display_name.lower()]
        if filtered:
            click.echo(f"Filtered to notebook: {filtered[0].display_name}")
            notebooks = filtered
        else:
            click.echo(f"Warning: notebook '{settings.notebook_name}' not found, showing all")

    nodes: list[HierarchyNode] = []

    for notebook in notebooks:
        click.echo(f"  Processing: {notebook.display_name}")
        sections = await client.list_sections(notebook.id)
        click.echo(f"    {len(sections)} section(s)")
        children: list[HierarchyNode] = []

        for section in sections:
            click.echo(f"    Scanning: {section.display_name}")
            pages = await client.list_pages(section.id)
            section_node = HierarchyNode(
                name=section.display_name,
                node_type="section",
                id=section.id,
                page_count=len(pages),
                page_ids=[p.id for p in pages],
                page_titles={p.id: p.title for p in pages},
            )
            children.append(section_node)

        notebook_node = HierarchyNode(
            name=notebook.display_name,
            node_type="notebook",
            id=notebook.id,
            children=children,
        )
        nodes.append(notebook_node)

    _save_cache(cache_file, nodes)
    return nodes


def _serialize_nodes(nodes: list[HierarchyNode]) -> list[dict[str, Any]]:
    """Sérialise une liste de nœuds en dictionnaires."""
    result: list[dict[str, Any]] = []
    for node in nodes:
        result.append(
            {
                "name": node.name,
                "node_type": node.node_type,
                "id": node.id,
                "page_count": node.page_count,
                "page_ids": node.page_ids,
                "page_titles": node.page_titles,
                "children": _serialize_nodes(node.children),
            }
        )
    return result


def _deserialize_nodes(data: list[dict[str, Any]]) -> list[HierarchyNode]:
    """Désérialise une liste de dictionnaires en nœuds."""
    result: list[HierarchyNode] = []
    for item in data:
        children = _deserialize_nodes(item.get("children", []))
        node = HierarchyNode(
            name=item["name"],
            node_type=item["node_type"],
            id=item["id"],
            page_count=item.get("page_count", 0),
            page_ids=item.get("page_ids", []),
            page_titles=item.get("page_titles", {}),
            children=children,
        )
        result.append(node)
    return result


def display_tree(nodes: list[HierarchyNode]) -> str:
    """Formate l'arbre pour affichage console.

    Args:
        nodes: Liste de nœuds à afficher.

    Returns:
        Représentation texte de l'arbre.
    """
    if not nodes:
        return ""

    lines: list[str] = []
    total_pages = 0

    for node in nodes:
        _display_node(node, 0, lines)
        total_pages += node.total_pages

    lines.append(f"\nTotal : {total_pages} pages")
    return "\n".join(lines)


def _display_node(node: HierarchyNode, indent: int, lines: list[str]) -> None:
    """Affiche récursivement un nœud et ses enfants."""
    prefix = "  " * indent
    if node.page_count > 0:
        line = f"{prefix}{node.name} ({node.page_count} pages)"
    else:
        line = f"{prefix}{node.name}"
    lines.append(line)

    for child in node.children:
        _display_node(child, indent + 1, lines)


def _add_node_to_rich_tree(node: HierarchyNode, parent_tree: Tree) -> None:
    """Ajoute récursivement un nœud HierarchyNode à un rich.Tree.

    Args:
        node: Le nœud à ajouter.
        parent_tree: L'objet Tree rich auquel rattacher ce nœud.
    """
    if node.node_type == "notebook":
        label = f"[bold cyan]{node.name}[/bold cyan]"
    elif node.node_type == "section_group":
        label = f"[yellow]{node.name}[/yellow]"
    else:
        label = f"[green]{node.name}[/green] [dim]({node.page_count} pages)[/dim]"

    branch = parent_tree.add(label)
    for child in node.children:
        _add_node_to_rich_tree(child, branch)


def display_tree_rich(nodes: list[HierarchyNode]) -> str:
    """Formate l'arbre OneNote avec couleurs rich pour affichage console.

    Args:
        nodes: Liste de nœuds racine (notebooks) à afficher.

    Returns:
        Représentation colorée de l'arbre, capturée sous forme de string.
    """
    if not nodes:
        return ""

    total_pages = sum(n.total_pages for n in nodes)

    root = Tree("[bold]OneNote[/bold]")
    for node in nodes:
        _add_node_to_rich_tree(node, root)

    buf = StringIO()
    console = Console(file=buf, highlight=False, markup=True)
    console.print(root)
    console.print(f"\n[bold]Total : {total_pages} pages[/bold]")

    return buf.getvalue()
