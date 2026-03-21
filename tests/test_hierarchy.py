"""Tests pour le mapping de hiérarchie OneNote."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.graph import GraphClient, Notebook, Page, Section
from src.hierarchy import HierarchyNode, build_tree, display_tree, display_tree_rich


class TestHierarchyNodePageIds:
    """Tests pour le champ page_ids de HierarchyNode (H1)."""

    def test_hierarchy_node_has_page_ids_field(self) -> None:
        """HierarchyNode doit avoir un champ page_ids."""
        node = HierarchyNode(name="Section A", node_type="section", id="s-1", page_count=2)
        assert hasattr(node, "page_ids")

    def test_hierarchy_node_page_ids_defaults_to_empty_list(self) -> None:
        """page_ids doit valoir [] par défaut."""
        node = HierarchyNode(name="Section A", node_type="section", id="s-1")
        assert node.page_ids == []

    def test_hierarchy_node_page_ids_accepts_list_of_strings(self) -> None:
        """page_ids doit accepter une liste d'IDs."""
        node = HierarchyNode(
            name="Section A", node_type="section", id="s-1", page_ids=["p-1", "p-2"]
        )
        assert node.page_ids == ["p-1", "p-2"]


class TestBuildTreePopulatesPageIds:
    """Tests pour la population de page_ids dans build_tree (H1)."""

    @pytest.mark.asyncio
    async def test_build_tree_populates_page_ids_from_api(self) -> None:
        """build_tree doit peupler page_ids avec les IDs réels des pages."""
        mock_client = AsyncMock(spec=GraphClient)
        mock_client.list_notebooks.return_value = [
            Notebook(id="nb-1", display_name="Notebook A"),
        ]
        mock_client.list_sections.return_value = [
            Section(id="s-1", display_name="Section 1", notebook_id="nb-1"),
        ]
        mock_client.list_pages.return_value = [
            Page(
                id="p-1", title="Page 1", section_id="s-1", created_date_time="2026-01-01T00:00:00Z"
            ),
            Page(
                id="p-2", title="Page 2", section_id="s-1", created_date_time="2026-01-02T00:00:00Z"
            ),
        ]

        with patch("src.hierarchy.get_settings") as mock_settings:
            mock_settings.return_value.cache_dir = Path("/tmp/cache")
            mock_settings.return_value.cache_ttl_seconds = 3600
            mock_settings.return_value.notebook_name = ""
            nodes = await build_tree(mock_client, no_cache=True)

        section_node = nodes[0].children[0]
        assert section_node.page_ids == ["p-1", "p-2"]

    @pytest.mark.asyncio
    async def test_build_tree_page_ids_serialized_in_cache(self, tmp_path: Path) -> None:
        """Le cache JSON doit inclure page_ids."""
        mock_client = AsyncMock(spec=GraphClient)
        mock_client.list_notebooks.return_value = [Notebook(id="nb-1", display_name="NB")]
        mock_client.list_sections.return_value = [
            Section(id="s-1", display_name="Sec", notebook_id="nb-1")
        ]
        mock_client.list_pages.return_value = [
            Page(id="p-42", title="P", section_id="s-1", created_date_time="2026-01-01T00:00:00Z")
        ]

        with patch("src.hierarchy.get_settings") as mock_settings:
            mock_settings.return_value.cache_dir = tmp_path
            mock_settings.return_value.cache_ttl_seconds = 3600
            mock_settings.return_value.notebook_name = ""
            await build_tree(mock_client, no_cache=False)

        with open(tmp_path / "hierarchy.json") as f:
            cached = json.load(f)

        section_cached = cached[0]["children"][0]
        assert "page_ids" in section_cached
        assert section_cached["page_ids"] == ["p-42"]

    @pytest.mark.asyncio
    async def test_build_tree_page_ids_deserialized_from_cache(self, tmp_path: Path) -> None:
        """Les page_ids doivent être restaurés depuis le cache."""
        cache_file = tmp_path / "hierarchy.json"
        cache_data = [
            {
                "name": "NB",
                "node_type": "notebook",
                "id": "nb-1",
                "page_count": 0,
                "page_ids": [],
                "children": [
                    {
                        "name": "Sec",
                        "node_type": "section",
                        "id": "s-1",
                        "page_count": 1,
                        "page_ids": ["p-cached"],
                        "children": [],
                    }
                ],
            }
        ]
        cache_file.write_text(json.dumps(cache_data))

        mock_client = AsyncMock(spec=GraphClient)
        with patch("src.hierarchy.get_settings") as mock_settings:
            mock_settings.return_value.cache_dir = tmp_path
            mock_settings.return_value.cache_ttl_seconds = 3600
            mock_settings.return_value.notebook_name = ""
            nodes = await build_tree(mock_client, no_cache=False)

        assert nodes[0].children[0].page_ids == ["p-cached"]


class TestHierarchyNode:
    """Tests pour la structure de l'arbre de hiérarchie."""

    def test_leaf_node_total_pages_equals_page_count(self) -> None:
        """Un nœud feuille doit avoir total_pages == page_count."""
        node = HierarchyNode(name="Section A", node_type="section", id="s-1", page_count=12)
        assert node.total_pages == 12

    def test_parent_node_sums_children_pages(self) -> None:
        """Un nœud parent doit sommer les pages de ses enfants."""
        child_a = HierarchyNode(name="A", node_type="section", id="s-1", page_count=10)
        child_b = HierarchyNode(name="B", node_type="section", id="s-2", page_count=5)
        parent = HierarchyNode(
            name="Notebook", node_type="notebook", id="nb-1", children=[child_a, child_b]
        )
        assert parent.total_pages == 15

    def test_nested_hierarchy_counts_all_levels(self) -> None:
        """Le comptage doit traverser tous les niveaux de profondeur."""
        page = HierarchyNode(name="Sec", node_type="section", id="s-1", page_count=3)
        group = HierarchyNode(name="Group", node_type="section_group", id="g-1", children=[page])
        notebook = HierarchyNode(name="NB", node_type="notebook", id="nb-1", children=[group])
        assert notebook.total_pages == 3

    def test_empty_node_has_zero_pages(self) -> None:
        """Un nœud sans pages et sans enfants doit avoir 0 pages."""
        node = HierarchyNode(name="Vide", node_type="section", id="s-0")
        assert node.total_pages == 0


class TestBuildTree:
    """Tests pour la construction de l'arbre depuis l'API Graph."""

    @pytest.mark.asyncio
    async def test_build_tree_creates_nodes_from_graph_client(self) -> None:
        """build_tree doit créer des nœuds HierarchyNode depuis GraphClient."""
        # Arrange
        mock_client = AsyncMock(spec=GraphClient)
        mock_client.list_notebooks.return_value = [
            Notebook(id="nb-1", display_name="Notebook A"),
        ]
        mock_client.list_sections.return_value = [
            Section(id="s-1", display_name="Section 1", notebook_id="nb-1"),
        ]
        mock_client.list_pages.return_value = [
            Page(
                id="p-1", title="Page 1", section_id="s-1", created_date_time="2026-01-01T00:00:00Z"
            ),
            Page(
                id="p-2", title="Page 2", section_id="s-1", created_date_time="2026-01-02T00:00:00Z"
            ),
        ]

        # Act
        with patch("src.hierarchy.get_settings") as mock_settings:
            mock_settings.return_value.cache_dir = Path("/tmp/cache")
            mock_settings.return_value.cache_ttl_seconds = 3600
            mock_settings.return_value.notebook_name = ""
            nodes = await build_tree(mock_client, no_cache=True)

        # Assert
        assert len(nodes) == 1
        assert nodes[0].name == "Notebook A"
        assert nodes[0].node_type == "notebook"
        assert nodes[0].id == "nb-1"
        assert len(nodes[0].children) == 1
        assert nodes[0].children[0].name == "Section 1"
        assert nodes[0].children[0].page_count == 2

    @pytest.mark.asyncio
    async def test_build_tree_caches_result_to_json(self, tmp_path: Path) -> None:
        """build_tree doit écrire le résultat en cache JSON."""
        # Arrange
        mock_client = AsyncMock(spec=GraphClient)
        mock_client.list_notebooks.return_value = [
            Notebook(id="nb-1", display_name="Test NB"),
        ]
        mock_client.list_sections.return_value = []
        mock_client.list_pages.return_value = []

        cache_file = tmp_path / "hierarchy.json"

        # Act
        with patch("src.hierarchy.get_settings") as mock_settings:
            mock_settings.return_value.cache_dir = tmp_path
            mock_settings.return_value.cache_ttl_seconds = 3600
            mock_settings.return_value.notebook_name = ""
            await build_tree(mock_client, no_cache=False)

        # Assert
        assert cache_file.exists()
        with open(cache_file) as f:
            cached = json.load(f)
        assert len(cached) == 1
        assert cached[0]["name"] == "Test NB"

    @pytest.mark.asyncio
    async def test_build_tree_reads_from_cache(self, tmp_path: Path) -> None:
        """build_tree doit lire depuis le cache si valide."""
        # Arrange
        cache_file = tmp_path / "hierarchy.json"
        cache_data = [
            {
                "name": "Cached Notebook",
                "node_type": "notebook",
                "id": "cached-nb-1",
                "page_count": 0,
                "children": [],
            }
        ]
        cache_file.write_text(json.dumps(cache_data))

        mock_client = AsyncMock(spec=GraphClient)

        # Act
        with patch("src.hierarchy.get_settings") as mock_settings:
            mock_settings.return_value.cache_dir = tmp_path
            mock_settings.return_value.cache_ttl_seconds = 3600
            mock_settings.return_value.notebook_name = ""
            nodes = await build_tree(mock_client, no_cache=False)

        # Assert
        assert len(nodes) == 1
        assert nodes[0].name == "Cached Notebook"
        mock_client.list_notebooks.assert_not_called()

    @pytest.mark.asyncio
    async def test_build_tree_no_cache_skips_cache(self, tmp_path: Path) -> None:
        """build_tree avec no_cache=True doit ignorer le cache."""
        # Arrange
        cache_file = tmp_path / "hierarchy.json"
        cache_data = [
            {
                "name": "Old Cached",
                "node_type": "notebook",
                "id": "old-1",
                "page_count": 0,
                "children": [],
            }
        ]
        cache_file.write_text(json.dumps(cache_data))

        mock_client = AsyncMock(spec=GraphClient)
        mock_client.list_notebooks.return_value = [
            Notebook(id="new-1", display_name="Fresh Data"),
        ]
        mock_client.list_sections.return_value = []
        mock_client.list_pages.return_value = []

        # Act
        with patch("src.hierarchy.get_settings") as mock_settings:
            mock_settings.return_value.cache_dir = tmp_path
            mock_settings.return_value.cache_ttl_seconds = 3600
            mock_settings.return_value.notebook_name = ""
            nodes = await build_tree(mock_client, no_cache=True)

        # Assert
        assert len(nodes) == 1
        assert nodes[0].name == "Fresh Data"
        assert nodes[0].id == "new-1"
        mock_client.list_notebooks.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_tree_cache_expired_refetches(self, tmp_path: Path) -> None:
        """build_tree doit refetcher si le cache a expiré."""
        # Arrange
        cache_file = tmp_path / "hierarchy.json"
        cache_data = [
            {
                "name": "Expired",
                "node_type": "notebook",
                "id": "exp-1",
                "page_count": 0,
                "children": [],
            }
        ]
        cache_file.write_text(json.dumps(cache_data))
        # Simuler une cache très ancienne en modifiant le timestamp
        cache_file.touch()

        mock_client = AsyncMock(spec=GraphClient)
        mock_client.list_notebooks.return_value = [
            Notebook(id="fresh-1", display_name="Refreshed"),
        ]
        mock_client.list_sections.return_value = []
        mock_client.list_pages.return_value = []

        # Act
        with patch("src.hierarchy.get_settings") as mock_settings:
            mock_settings.return_value.cache_dir = tmp_path
            mock_settings.return_value.cache_ttl_seconds = (
                0  # TTL = 0 pour forcer expiration immédiate
            )
            mock_settings.return_value.notebook_name = ""
            with patch("time.time", return_value=cache_file.stat().st_mtime + 1):
                nodes = await build_tree(mock_client, no_cache=False)

        # Assert
        assert len(nodes) == 1
        assert nodes[0].name == "Refreshed"
        mock_client.list_notebooks.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_tree_corrupt_cache_refetches(self, tmp_path: Path) -> None:
        """build_tree doit ignorer un cache corrompu et refetcher depuis l'API."""
        cache_file = tmp_path / "hierarchy.json"
        cache_file.write_text("{invalid json")

        mock_client = AsyncMock(spec=GraphClient)
        mock_client.list_notebooks.return_value = [
            Notebook(id="nb-1", display_name="Fresh"),
        ]
        mock_client.list_sections.return_value = []
        mock_client.list_pages.return_value = []

        with patch("src.hierarchy.get_settings") as mock_settings:
            mock_settings.return_value.cache_dir = tmp_path
            mock_settings.return_value.cache_ttl_seconds = 3600
            mock_settings.return_value.notebook_name = ""
            nodes = await build_tree(mock_client, no_cache=False)

        assert nodes[0].name == "Fresh"
        mock_client.list_notebooks.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_tree_returns_empty_list_when_no_notebooks(self) -> None:
        """build_tree doit retourner une liste vide si pas de notebooks."""
        # Arrange
        mock_client = AsyncMock(spec=GraphClient)
        mock_client.list_notebooks.return_value = []

        # Act
        with patch("src.hierarchy.get_settings") as mock_settings:
            mock_settings.return_value.cache_dir = Path("/tmp/cache")
            mock_settings.return_value.cache_ttl_seconds = 3600
            mock_settings.return_value.notebook_name = ""
            nodes = await build_tree(mock_client, no_cache=True)

        # Assert
        assert nodes == []


class TestDisplayTree:
    """Tests pour l'affichage formaté de l'arbre."""

    def test_display_tree_shows_page_counts(self) -> None:
        """display_tree doit afficher le format '(N pages)' pour les comptages."""
        # Arrange
        section = HierarchyNode(name="Section A", node_type="section", id="s-1", page_count=5)
        notebook = HierarchyNode(
            name="Notebook", node_type="notebook", id="nb-1", children=[section]
        )

        # Act
        output = display_tree([notebook])

        # Assert
        assert "(5 pages)" in output or "5" in output

    def test_display_tree_shows_total(self) -> None:
        """display_tree doit afficher le total de pages à la fin."""
        # Arrange
        section_a = HierarchyNode(name="Section A", node_type="section", id="s-1", page_count=10)
        section_b = HierarchyNode(name="Section B", node_type="section", id="s-2", page_count=15)
        notebook = HierarchyNode(
            name="Notebook",
            node_type="notebook",
            id="nb-1",
            children=[section_a, section_b],
        )

        # Act
        output = display_tree([notebook])

        # Assert
        # Doit afficher le total quelque part
        assert "25" in output or "total" in output.lower()

    def test_display_tree_empty_tree(self) -> None:
        """display_tree doit gérer une liste vide sans erreur."""
        # Act
        output = display_tree([])

        # Assert
        assert isinstance(output, str)

    def test_display_tree_single_node(self) -> None:
        """display_tree doit afficher un seul nœud sans enfants."""
        # Arrange
        notebook = HierarchyNode(name="My Notebook", node_type="notebook", id="nb-1", page_count=0)

        # Act
        output = display_tree([notebook])

        # Assert
        assert "My Notebook" in output

    def test_display_tree_nested_structure(self) -> None:
        """display_tree doit afficher la structure imbriquée avec indentation."""
        # Arrange
        section = HierarchyNode(name="Section 1", node_type="section", id="s-1", page_count=3)
        group = HierarchyNode(name="Group", node_type="section_group", id="g-1", children=[section])
        notebook = HierarchyNode(name="NB", node_type="notebook", id="nb-1", children=[group])

        # Act
        output = display_tree([notebook])

        # Assert
        assert "NB" in output
        assert "Group" in output
        assert "Section 1" in output

    def test_display_tree_multiple_notebooks(self) -> None:
        """display_tree doit afficher plusieurs notebooks."""
        # Arrange
        nb1 = HierarchyNode(name="Notebook 1", node_type="notebook", id="nb-1", page_count=5)
        nb2 = HierarchyNode(name="Notebook 2", node_type="notebook", id="nb-2", page_count=10)

        # Act
        output = display_tree([nb1, nb2])

        # Assert
        assert "Notebook 1" in output
        assert "Notebook 2" in output


class TestDisplayTreeRich:
    """Tests pour l'affichage coloré de l'arbre avec rich (CDC §2.2)."""

    def test_display_tree_rich_shows_notebook_name(self) -> None:
        """Le nom du notebook doit apparaître dans la sortie."""
        notebook = HierarchyNode(name="Mon Notebook", node_type="notebook", id="nb-1")
        output = display_tree_rich([notebook])
        assert "Mon Notebook" in output

    def test_display_tree_rich_shows_section_page_count(self) -> None:
        """Le compteur de pages doit apparaître pour les sections."""
        section = HierarchyNode(name="Section A", node_type="section", id="s-1", page_count=12)
        notebook = HierarchyNode(name="NB", node_type="notebook", id="nb-1", children=[section])
        output = display_tree_rich([notebook])
        assert "Section A" in output
        assert "12" in output

    def test_display_tree_rich_shows_total(self) -> None:
        """Le total de pages doit apparaître en bas."""
        section_a = HierarchyNode(name="Section A", node_type="section", id="s-1", page_count=200)
        section_b = HierarchyNode(name="Section B", node_type="section", id="s-2", page_count=147)
        notebook = HierarchyNode(
            name="NB",
            node_type="notebook",
            id="nb-1",
            children=[section_a, section_b],
        )
        output = display_tree_rich([notebook])
        assert "347" in output
        assert "Total" in output

    def test_display_tree_rich_handles_empty_tree(self) -> None:
        """Un arbre vide doit retourner une string vide ou minimale."""
        output = display_tree_rich([])
        assert isinstance(output, str)
        assert "Total" not in output

    def test_display_tree_rich_shows_nested_structure(self) -> None:
        """Les sections imbriquées dans des groupes doivent apparaître."""
        section = HierarchyNode(name="Section 1", node_type="section", id="s-1", page_count=3)
        group = HierarchyNode(
            name="Mon Groupe", node_type="section_group", id="g-1", children=[section]
        )
        notebook = HierarchyNode(name="NB", node_type="notebook", id="nb-1", children=[group])
        output = display_tree_rich([notebook])
        assert "NB" in output
        assert "Mon Groupe" in output
        assert "Section 1" in output

    def test_display_tree_rich_multiple_notebooks(self) -> None:
        """Plusieurs notebooks doivent tous être affichés."""
        nb1 = HierarchyNode(name="Notebook Alpha", node_type="notebook", id="nb-1")
        nb2 = HierarchyNode(name="Notebook Beta", node_type="notebook", id="nb-2")
        output = display_tree_rich([nb1, nb2])
        assert "Notebook Alpha" in output
        assert "Notebook Beta" in output


class TestBuildTreeNotebookFilter:
    """Tests pour le filtrage par notebook_name dans build_tree."""

    @pytest.mark.asyncio
    async def test_build_tree_filters_by_notebook_name(self, tmp_path: Path) -> None:
        """build_tree doit filtrer les notebooks par nom si notebook_name est configuré."""
        mock_client = AsyncMock(spec=GraphClient)
        mock_client.list_notebooks.return_value = [
            Notebook(id="nb-1", display_name="The Process"),
            Notebook(id="nb-2", display_name="Other Notebook"),
        ]
        mock_client.list_sections.return_value = []
        mock_client.list_pages.return_value = []

        with patch("src.hierarchy.get_settings") as mock_settings:
            mock_settings.return_value.cache_dir = tmp_path
            mock_settings.return_value.cache_ttl_seconds = 3600
            mock_settings.return_value.notebook_name = "Process"
            nodes = await build_tree(mock_client, no_cache=True)

        assert len(nodes) == 1
        assert nodes[0].name == "The Process"

    @pytest.mark.asyncio
    async def test_build_tree_no_filter_when_empty_name(self, tmp_path: Path) -> None:
        """build_tree ne doit pas filtrer si notebook_name est vide."""
        mock_client = AsyncMock(spec=GraphClient)
        mock_client.list_notebooks.return_value = [
            Notebook(id="nb-1", display_name="NB 1"),
            Notebook(id="nb-2", display_name="NB 2"),
        ]
        mock_client.list_sections.return_value = []
        mock_client.list_pages.return_value = []

        with patch("src.hierarchy.get_settings") as mock_settings:
            mock_settings.return_value.cache_dir = tmp_path
            mock_settings.return_value.cache_ttl_seconds = 3600
            mock_settings.return_value.notebook_name = ""
            nodes = await build_tree(mock_client, no_cache=True)

        assert len(nodes) == 2

    @pytest.mark.asyncio
    async def test_build_tree_shows_all_if_notebook_not_found(self, tmp_path: Path) -> None:
        """build_tree doit montrer tous les notebooks si le filtre ne matche rien."""
        mock_client = AsyncMock(spec=GraphClient)
        mock_client.list_notebooks.return_value = [
            Notebook(id="nb-1", display_name="NB 1"),
        ]
        mock_client.list_sections.return_value = []
        mock_client.list_pages.return_value = []

        with patch("src.hierarchy.get_settings") as mock_settings:
            mock_settings.return_value.cache_dir = tmp_path
            mock_settings.return_value.cache_ttl_seconds = 3600
            mock_settings.return_value.notebook_name = "NonExistent"
            nodes = await build_tree(mock_client, no_cache=True)

        assert len(nodes) == 1  # fallback: show all
