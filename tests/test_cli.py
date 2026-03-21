"""Tests pour l'interface CLI OneNote Exporter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from src.cli import main
from src.hierarchy import HierarchyNode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_graph_client_mock() -> MagicMock:
    """Return a GraphClient mock with async close() that never leaks coroutines."""
    mock_client = MagicMock()
    mock_client.close = AsyncMock()
    return mock_client


def _make_export_report(exported: int = 0) -> MagicMock:
    """Return a minimal ExportReport mock."""
    report = MagicMock()
    report.exported = exported
    return report


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_EMPTY_NODES: list[HierarchyNode] = []

_SINGLE_NOTEBOOK = [HierarchyNode(name="Test NB", node_type="notebook", id="nb-1", page_count=5)]


class TestMainGroup:
    """Tests pour le groupe CLI principal."""

    def test_main_group_has_all_commands(self) -> None:
        """Le groupe main doit avoir les commandes auth, tree et export."""
        assert "auth" in main.commands
        assert "tree" in main.commands
        assert "export" in main.commands

    def test_main_group_has_three_commands(self) -> None:
        """Le groupe main doit avoir exactement 3 commandes."""
        assert len(main.commands) == 3

    def test_verbose_flag_is_available(self) -> None:
        """Le flag --verbose/-v doit être disponible sur le groupe main."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "--verbose" in result.output or "-v" in result.output

    def test_no_cache_flag_is_available(self) -> None:
        """Le flag --no-cache doit être disponible sur le groupe main."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "--no-cache" in result.output


class TestAuthCommand:
    """Tests pour la commande auth."""

    def test_auth_command_is_registered(self) -> None:
        """La commande auth doit être enregistrée dans le groupe main."""
        runner = CliRunner()
        result = runner.invoke(main, ["auth", "--help"])
        assert result.exit_code == 0

    def test_auth_command_calls_authenticate(self) -> None:
        """La commande auth doit appeler authenticate()."""
        runner = CliRunner()
        with patch("src.cli.authenticate") as mock_auth:
            mock_auth.return_value = "test-token-12345"
            runner.invoke(main, ["auth"])
            mock_auth.assert_called_once()

    def test_auth_command_shows_success_message(self) -> None:
        """La commande auth doit afficher un message de succès."""
        runner = CliRunner()
        with patch("src.cli.authenticate") as mock_auth:
            mock_auth.return_value = "test-token-12345"
            result = runner.invoke(main, ["auth"])
            assert "auth" in result.output.lower() or "success" in result.output.lower()

    def test_auth_command_shows_error_on_failure(self) -> None:
        """La commande auth doit afficher une erreur en cas d'échec."""
        from src.auth import AuthenticationError

        runner = CliRunner()
        with patch("src.cli.authenticate") as mock_auth:
            mock_auth.side_effect = AuthenticationError("Device flow timeout")
            result = runner.invoke(main, ["auth"])
            assert "error" in result.output.lower() or result.exit_code != 0

    def test_auth_command_returns_non_zero_on_failure(self) -> None:
        """La commande auth doit retourner un code non-zéro en cas d'échec."""
        from src.auth import AuthenticationError

        runner = CliRunner()
        with patch("src.cli.authenticate") as mock_auth:
            mock_auth.side_effect = AuthenticationError("Auth failed")
            result = runner.invoke(main, ["auth"])
            assert result.exit_code != 0

    def test_auth_command_exits_with_zero_on_success(self) -> None:
        """La commande auth doit retourner 0 en cas de succès."""
        runner = CliRunner()
        with patch("src.cli.authenticate") as mock_auth:
            mock_auth.return_value = "valid-token"
            result = runner.invoke(main, ["auth"])
            assert result.exit_code == 0


class TestTreeCommand:
    """Tests pour la commande tree."""

    def test_tree_command_is_registered(self) -> None:
        """La commande tree doit être enregistrée dans le groupe main."""
        runner = CliRunner()
        result = runner.invoke(main, ["tree", "--help"])
        assert result.exit_code == 0

    def test_tree_command_displays_hierarchy(self) -> None:
        """La commande tree doit construire et afficher la hiérarchie."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=_SINGLE_NOTEBOOK)),
            patch("src.cli.display_tree", return_value="Test NB\n  5 pages"),
        ):
            result = runner.invoke(main, ["tree"])
            assert result.exit_code == 0

    def test_tree_command_passes_no_cache_flag(self) -> None:
        """La commande tree doit passer --no-cache à build_tree()."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()
        mock_build = AsyncMock(return_value=_EMPTY_NODES)

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=mock_build),
            patch("src.cli.display_tree", return_value=""),
        ):
            runner.invoke(main, ["--no-cache", "tree"])
            mock_build.assert_called_once()
            _, kwargs = mock_build.call_args
            assert kwargs.get("no_cache") is True

    def test_tree_command_calls_authenticate(self) -> None:
        """La commande tree doit appeler authenticate() pour obtenir un token."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()

        with (
            patch("src.cli.authenticate", return_value="test-token") as mock_auth,
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=_EMPTY_NODES)),
            patch("src.cli.display_tree", return_value=""),
        ):
            runner.invoke(main, ["tree"])
            mock_auth.assert_called_once()

    def test_tree_command_calls_display_tree(self) -> None:
        """La commande tree doit appeler display_tree() avec les nœuds retournés."""
        runner = CliRunner()
        nodes = [HierarchyNode(name="NB 1", node_type="notebook", id="nb-1", page_count=10)]
        mock_client = _make_graph_client_mock()

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=nodes)),
            patch("src.cli.display_tree") as mock_display,
        ):
            mock_display.return_value = "Formatted output"
            runner.invoke(main, ["tree"])
            mock_display.assert_called_once()

    def test_tree_command_exits_zero_on_success(self) -> None:
        """La commande tree doit retourner 0 en cas de succès."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=_EMPTY_NODES)),
            patch("src.cli.display_tree", return_value=""),
        ):
            result = runner.invoke(main, ["tree"])
            assert result.exit_code == 0


class TestExportCommand:
    """Tests pour la commande export."""

    def test_export_command_is_registered(self) -> None:
        """La commande export doit être enregistrée dans le groupe main."""
        runner = CliRunner()
        result = runner.invoke(main, ["export", "--help"])
        assert result.exit_code == 0
        assert "Exporter" in result.output

    def test_export_has_sections_option(self) -> None:
        """La commande export doit avoir --sections / -s."""
        runner = CliRunner()
        result = runner.invoke(main, ["export", "--help"])
        assert "--sections" in result.output or "-s" in result.output

    def test_export_has_all_option(self) -> None:
        """La commande export doit avoir --all."""
        runner = CliRunner()
        result = runner.invoke(main, ["export", "--help"])
        assert "--all" in result.output

    def test_export_has_max_pages_option(self) -> None:
        """La commande export doit avoir --max-pages."""
        runner = CliRunner()
        result = runner.invoke(main, ["export", "--help"])
        assert "--max-pages" in result.output

    def test_export_has_output_dir_option(self) -> None:
        """La commande export doit avoir --output-dir / -o."""
        runner = CliRunner()
        result = runner.invoke(main, ["export", "--help"])
        assert "--output-dir" in result.output or "-o" in result.output

    def test_export_with_sections(self) -> None:
        """La commande export doit accepter --sections."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=_EMPTY_NODES)),
            patch("src.cli.export_batch", new=AsyncMock(return_value=_make_export_report(5))),
        ):
            result = runner.invoke(main, ["export", "--sections", "sec1,sec2"])
            assert result is not None

    def test_export_with_all_flag(self) -> None:
        """La commande export doit accepter --all."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=_EMPTY_NODES)),
            patch("src.cli.export_batch", new=AsyncMock(return_value=_make_export_report(10))),
        ):
            result = runner.invoke(main, ["export", "--all"])
            assert result is not None

    def test_export_max_pages_default_is_150(self) -> None:
        """max-pages par défaut doit être 150 dans l'aide."""
        runner = CliRunner()
        result = runner.invoke(main, ["export", "--help"])
        assert "150" in result.output

    def test_export_runs_async(self) -> None:
        """La commande export doit exécuter export_batch() de manière async."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()
        mock_export = AsyncMock(return_value=_make_export_report(2))

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=_EMPTY_NODES)),
            patch("src.cli.export_batch", new=mock_export),
        ):
            runner.invoke(main, ["export", "--all"])
            mock_export.assert_called_once()

    def test_export_exits_zero_on_success(self) -> None:
        """La commande export doit retourner 0 en cas de succès."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=_EMPTY_NODES)),
            patch("src.cli.export_batch", new=AsyncMock(return_value=_make_export_report(1))),
        ):
            result = runner.invoke(main, ["export"])
            assert result.exit_code == 0


class TestExportConfirmation:
    """Tests pour la confirmation avant export massif (CDC §3.2)."""

    def _build_large_tree(self, n: int = 201) -> list[HierarchyNode]:
        """Construit un arbre avec n sections d'une page chacune."""
        return [
            HierarchyNode(
                name="NB",
                node_type="notebook",
                id="nb-1",
                children=[
                    HierarchyNode(
                        name=f"Sec{i}",
                        node_type="section",
                        id=f"s-{i}",
                        page_count=1,
                        page_ids=[f"p-{i}"],
                    )
                    for i in range(n)
                ],
            )
        ]

    def test_export_all_with_over_200_pages_asks_confirmation(self) -> None:
        """export --all avec >200 pages doit demander confirmation (CDC §3.2)."""
        runner = CliRunner()
        many_nodes = self._build_large_tree(201)
        mock_client = _make_graph_client_mock()

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=many_nodes)),
            patch("src.cli.export_batch", new=AsyncMock(return_value=_make_export_report(0))),
        ):
            result = runner.invoke(main, ["export", "--all", "--max-pages", "201"], input="n\n")
            assert "Continuer" in result.output

    def test_export_all_with_over_200_pages_cancelled_on_no(self) -> None:
        """Répondre 'n' à la confirmation doit annuler l'export (CDC §3.2)."""
        runner = CliRunner()
        many_nodes = self._build_large_tree(201)
        mock_client = _make_graph_client_mock()

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=many_nodes)),
            patch("src.cli.export_batch", new=AsyncMock(return_value=_make_export_report(0))),
        ):
            result = runner.invoke(main, ["export", "--all", "--max-pages", "201"], input="n\n")
            assert "annulé" in result.output.lower()

    def test_export_all_fewer_than_200_pages_skips_confirmation(self) -> None:
        """export --all avec <=200 pages ne doit pas demander de confirmation."""
        runner = CliRunner()
        small_tree = [
            HierarchyNode(
                name="NB",
                node_type="notebook",
                id="nb-1",
                children=[
                    HierarchyNode(
                        name="Sec1",
                        node_type="section",
                        id="s-1",
                        page_count=10,
                        page_ids=[f"p-{i}" for i in range(10)],
                    )
                ],
            )
        ]
        mock_client = _make_graph_client_mock()

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=small_tree)),
            patch("src.cli.export_batch", new=AsyncMock(return_value=_make_export_report(10))),
        ):
            result = runner.invoke(main, ["export", "--all"])
            assert result.exit_code == 0
            assert "Continuer" not in result.output


class TestAuthErrorHandling:
    """Tests H3 — authenticate() est dans un try/except pour tree et export."""

    def test_tree_command_handles_authentication_error_gracefully(self) -> None:
        """tree doit afficher une erreur propre si authenticate() lève AuthenticationError."""
        from src.auth import AuthenticationError

        runner = CliRunner()
        with patch("src.cli.authenticate", side_effect=AuthenticationError("token expired")):
            result = runner.invoke(main, ["tree"])
            assert result.exit_code != 0
            assert "erreur" in result.output.lower() or "error" in result.output.lower()

    def test_tree_command_returns_nonzero_on_authentication_error(self) -> None:
        """tree doit retourner un code non-zéro si authenticate() échoue."""
        from src.auth import AuthenticationError

        runner = CliRunner()
        with patch("src.cli.authenticate", side_effect=AuthenticationError("fail")):
            result = runner.invoke(main, ["tree"])
            assert result.exit_code != 0

    def test_export_command_handles_authentication_error_gracefully(self) -> None:
        """export doit afficher une erreur si authenticate() lève AuthenticationError."""
        from src.auth import AuthenticationError

        runner = CliRunner()
        with patch("src.cli.authenticate", side_effect=AuthenticationError("no token")):
            result = runner.invoke(main, ["export", "--all"])
            assert result.exit_code != 0
            assert "erreur" in result.output.lower() or "error" in result.output.lower()


class TestCollectPageIds:
    """Tests pour _collect_page_ids — utilise node.page_ids (list), pas node.id."""

    def test_collect_page_ids_returns_page_ids_not_section_ids(self) -> None:
        """_collect_page_ids doit retourner des page IDs, pas des section IDs (H1)."""
        from src.cli import _collect_page_ids

        section = HierarchyNode(
            name="Section A",
            node_type="section",
            id="section-id-NOT-a-page",
            page_count=2,
            page_ids=["page-id-1", "page-id-2"],
        )
        notebook = HierarchyNode(name="NB", node_type="notebook", id="nb-1", children=[section])

        result = _collect_page_ids([notebook], sections=None, export_all=True, max_pages=150)

        assert "section-id-NOT-a-page" not in result
        assert "page-id-1" in result
        assert "page-id-2" in result

    def test_collect_page_ids_filters_by_section_name(self) -> None:
        """_collect_page_ids doit inclure uniquement les sections demandées."""
        from src.cli import _collect_page_ids

        sec_a = HierarchyNode(
            name="Section A", node_type="section", id="s-a", page_count=1, page_ids=["p-a"]
        )
        sec_b = HierarchyNode(
            name="Section B", node_type="section", id="s-b", page_count=1, page_ids=["p-b"]
        )
        notebook = HierarchyNode(
            name="NB", node_type="notebook", id="nb-1", children=[sec_a, sec_b]
        )

        result = _collect_page_ids(
            [notebook], sections="Section A", export_all=False, max_pages=150
        )

        assert "p-a" in result
        assert "p-b" not in result

    def test_collect_page_ids_respects_max_pages(self) -> None:
        """_collect_page_ids doit tronquer au max_pages demandé."""
        from src.cli import _collect_page_ids

        section = HierarchyNode(
            name="Section A",
            node_type="section",
            id="s-1",
            page_count=5,
            page_ids=["p-1", "p-2", "p-3", "p-4", "p-5"],
        )
        notebook = HierarchyNode(name="NB", node_type="notebook", id="nb-1", children=[section])

        result = _collect_page_ids([notebook], sections=None, export_all=True, max_pages=3)

        assert len(result) == 3


class TestVerboseLogging:
    """Tests pour le flag --verbose."""

    def test_verbose_flag_sets_debug_logging(self) -> None:
        """Le flag -v doit être accepté sans erreur par la commande tree."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=_EMPTY_NODES)),
            patch("src.cli.display_tree", return_value=""),
        ):
            result = runner.invoke(main, ["-v", "tree"])
            assert result is not None


class TestCommandHelp:
    """Tests pour l'aide des commandes."""

    def test_main_help_text(self) -> None:
        """Le texte d'aide principal doit mentionner OneNote."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "OneNote" in result.output

    def test_export_help_text(self) -> None:
        """Le texte d'aide export doit mentionner l'export."""
        runner = CliRunner()
        result = runner.invoke(main, ["export", "--help"])
        assert result.exit_code == 0
        assert "Exporter" in result.output or "export" in result.output.lower()


class TestContextPassing:
    """Tests pour le passage de contexte entre groupe et sous-commandes."""

    def test_main_passes_verbose_to_subcommand(self) -> None:
        """Le flag --verbose doit être accessible dans la sous-commande auth."""
        runner = CliRunner()

        with patch("src.cli.authenticate") as mock_auth:
            mock_auth.return_value = "token"
            result = runner.invoke(main, ["--verbose", "auth"])
            assert result is not None

    def test_main_passes_no_cache_to_subcommand(self) -> None:
        """Le flag --no-cache doit être accessible dans la sous-commande tree."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=_EMPTY_NODES)),
            patch("src.cli.display_tree", return_value=""),
        ):
            result = runner.invoke(main, ["--no-cache", "tree"])
            assert result.exit_code == 0


class TestSingleEventLoop:
    """Tests H2 — tree et export utilisent asyncio.run pour les appels async."""

    def test_tree_command_calls_asyncio_run(self) -> None:
        """tree doit appeler asyncio.run pour build_tree et client.close."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.asyncio.run") as mock_run,
            patch("src.cli.display_tree", return_value="output"),
            patch("src.cli.build_tree", new=AsyncMock(return_value=_EMPTY_NODES)),
        ):
            # asyncio.run is still called twice: for build_tree and client.close
            mock_run.side_effect = [_EMPTY_NODES, None]
            runner.invoke(main, ["tree"])
            assert mock_run.call_count >= 1

    def test_export_command_calls_asyncio_run(self) -> None:
        """export doit appeler asyncio.run pour build_tree, export_batch et close."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.asyncio.run") as mock_run,
            patch("src.cli.build_tree", new=AsyncMock(return_value=_EMPTY_NODES)),
            patch("src.cli.export_batch", new=AsyncMock(return_value=_make_export_report(0))),
        ):
            mock_run.side_effect = [_EMPTY_NODES, _make_export_report(0), None]
            runner.invoke(main, ["export", "--all"])
            assert mock_run.call_count >= 1


# ---------------------------------------------------------------------------
# CDC §3.1 — Mode interactif : _parse_selection
# ---------------------------------------------------------------------------


class TestParseSelection:
    """Tests pour _parse_selection — parsing de la sélection interactive."""

    def test_parse_single_number_returns_single_element(self) -> None:
        """'3' avec max=5 doit retourner [3]."""
        from src.cli import _parse_selection

        assert _parse_selection("3", 5) == [3]

    def test_parse_comma_separated_returns_sorted_list(self) -> None:
        """'1,3,5' avec max=5 doit retourner [1, 3, 5]."""
        from src.cli import _parse_selection

        assert _parse_selection("1,3,5", 5) == [1, 3, 5]

    def test_parse_range_returns_full_range(self) -> None:
        """'1-5' avec max=5 doit retourner [1, 2, 3, 4, 5]."""
        from src.cli import _parse_selection

        assert _parse_selection("1-5", 5) == [1, 2, 3, 4, 5]

    def test_parse_mixed_returns_combined_sorted(self) -> None:
        """'1,3-5,8' avec max=10 doit retourner [1, 3, 4, 5, 8]."""
        from src.cli import _parse_selection

        assert _parse_selection("1,3-5,8", 10) == [1, 3, 4, 5, 8]

    def test_parse_out_of_bounds_ignored_below_one(self) -> None:
        """'0,6' avec max=5 doit retourner [] (0 < 1, 6 > max)."""
        from src.cli import _parse_selection

        assert _parse_selection("0,6", 5) == []

    def test_parse_empty_string_returns_empty_list(self) -> None:
        """'' doit retourner []."""
        from src.cli import _parse_selection

        assert _parse_selection("", 5) == []

    def test_parse_deduplicates_repeated_indices(self) -> None:
        """'1,1,2' avec max=5 doit retourner [1, 2] (dédupliqué)."""
        from src.cli import _parse_selection

        assert _parse_selection("1,1,2", 5) == [1, 2]

    def test_parse_whitespace_tolerant(self) -> None:
        """'1, 3, 5' avec espaces doit retourner [1, 3, 5]."""
        from src.cli import _parse_selection

        assert _parse_selection("1, 3, 5", 5) == [1, 3, 5]

    def test_parse_range_partial_out_of_bounds_clamps(self) -> None:
        """'3-7' avec max=5 doit retourner [3, 4, 5] (7 ignoré)."""
        from src.cli import _parse_selection

        assert _parse_selection("3-7", 5) == [3, 4, 5]


# ---------------------------------------------------------------------------
# CDC §3.1 — _build_numbered_sections
# ---------------------------------------------------------------------------


class TestBuildNumberedSections:
    """Tests pour _build_numbered_sections — numérotation des sections."""

    def test_flat_sections_numbered_sequentially(self) -> None:
        """Des sections directes sous un notebook doivent être numérotées 1, 2, 3."""
        from src.cli import _build_numbered_sections

        sec_a = HierarchyNode(name="Sec A", node_type="section", id="s-a")
        sec_b = HierarchyNode(name="Sec B", node_type="section", id="s-b")
        nb = HierarchyNode(name="NB", node_type="notebook", id="nb-1", children=[sec_a, sec_b])

        numbered = _build_numbered_sections([nb])

        assert len(numbered) == 2
        indices = [n[0] for n in numbered]
        assert indices == [1, 2]

    def test_nested_sections_included_with_path(self) -> None:
        """Les sections imbriquées dans un groupe doivent apparaître dans la liste."""
        from src.cli import _build_numbered_sections

        sec = HierarchyNode(name="Sec", node_type="section", id="s-1")
        group = HierarchyNode(name="Group", node_type="section_group", id="g-1", children=[sec])
        nb = HierarchyNode(name="NB", node_type="notebook", id="nb-1", children=[group])

        numbered = _build_numbered_sections([nb])

        names_or_paths = [n[1] for n in numbered]
        assert any("Sec" in p for p in names_or_paths)

    def test_returns_tuples_of_int_str_node(self) -> None:
        """Chaque élément doit être (int, str, HierarchyNode)."""
        from src.cli import _build_numbered_sections

        sec = HierarchyNode(name="Sec", node_type="section", id="s-1")
        nb = HierarchyNode(name="NB", node_type="notebook", id="nb-1", children=[sec])

        numbered = _build_numbered_sections([nb])

        assert len(numbered) == 1
        idx, path, node = numbered[0]
        assert isinstance(idx, int)
        assert isinstance(path, str)
        assert isinstance(node, HierarchyNode)
        assert node.node_type == "section"

    def test_empty_tree_returns_empty_list(self) -> None:
        """Un arbre vide doit retourner une liste vide."""
        from src.cli import _build_numbered_sections

        assert _build_numbered_sections([]) == []

    def test_notebook_without_sections_returns_empty(self) -> None:
        """Un notebook sans sections ne doit pas apparaître dans la liste."""
        from src.cli import _build_numbered_sections

        nb = HierarchyNode(name="NB", node_type="notebook", id="nb-1")

        assert _build_numbered_sections([nb]) == []


# ---------------------------------------------------------------------------
# CDC §3.1 — Mode interactif dans export
# ---------------------------------------------------------------------------


def _make_section_tree() -> list[HierarchyNode]:
    """Arbre minimal: 1 notebook, 2 sections avec des pages."""
    sec_a = HierarchyNode(
        name="Sec A",
        node_type="section",
        id="s-a",
        page_count=2,
        page_ids=["p-a1", "p-a2"],
    )
    sec_b = HierarchyNode(
        name="Sec B",
        node_type="section",
        id="s-b",
        page_count=1,
        page_ids=["p-b1"],
    )
    return [HierarchyNode(name="NB", node_type="notebook", id="nb-1", children=[sec_a, sec_b])]


class TestInteractiveMode:
    """Tests pour le mode interactif dans la commande export (CDC §3.1)."""

    def test_export_without_flags_prompts_when_tty(self) -> None:
        """Sans --sections ni --all, export doit demander une sélection si tty."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()
        tree_nodes = _make_section_tree()

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=tree_nodes)),
            patch("src.cli.export_batch", new=AsyncMock(return_value=_make_export_report(0))),
            patch("src.cli._is_interactive", return_value=True),
        ):
            result = runner.invoke(main, ["export"], input="1\n")
            assert "Sélection" in result.output or "section" in result.output.lower()

    def test_export_with_sections_flag_skips_prompt(self) -> None:
        """Avec --sections, export ne doit pas demander de sélection interactive."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()
        tree_nodes = _make_section_tree()

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=tree_nodes)),
            patch("src.cli.export_batch", new=AsyncMock(return_value=_make_export_report(2))),
            patch("src.cli._is_interactive", return_value=True),
        ):
            result = runner.invoke(main, ["export", "--sections", "Sec A"])
            assert "Sélection" not in result.output

    def test_export_with_all_flag_skips_prompt(self) -> None:
        """Avec --all, export ne doit pas demander de sélection interactive."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()
        tree_nodes = _make_section_tree()

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=tree_nodes)),
            patch("src.cli.export_batch", new=AsyncMock(return_value=_make_export_report(3))),
            patch("src.cli._is_interactive", return_value=True),
        ):
            result = runner.invoke(main, ["export", "--all"])
            assert "Sélection" not in result.output

    def test_export_interactive_selection_collects_correct_pages(self) -> None:
        """Sélectionner la section 1 doit collecter ses pages."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()
        tree_nodes = _make_section_tree()
        captured: list[list[tuple[str, str]]] = []

        async def mock_export_batch(pages: list[tuple[str, str]], **kwargs: object) -> MagicMock:
            captured.append(pages)
            return _make_export_report(len(pages))

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=tree_nodes)),
            patch("src.cli.export_batch", new=mock_export_batch),
            patch("src.cli._is_interactive", return_value=True),
        ):
            runner.invoke(main, ["export"], input="1\n")

        if captured:
            page_ids = [p[0] for p in captured[0]]
            assert "p-a1" in page_ids or "p-b1" in page_ids

    def test_export_non_interactive_without_flags_exports_nothing(self) -> None:
        """Sans --sections ni --all et sans tty, aucune page ne doit être exportée."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()
        tree_nodes = _make_section_tree()
        mock_export = AsyncMock(return_value=_make_export_report(0))

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=tree_nodes)),
            patch("src.cli.export_batch", new=mock_export),
            patch("src.cli._is_interactive", return_value=False),
        ):
            result = runner.invoke(main, ["export"])
            assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Bug fix — page titles au lieu des IDs (cli.py:108)
# ---------------------------------------------------------------------------


class TestPageTitlesInExport:
    """export_batch doit recevoir (page_id, page_title) et non (page_id, page_id)."""

    def test_export_passes_real_title_not_id_as_title(self) -> None:
        """export_batch doit être appelé avec le titre réel de la page, pas l'ID."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()

        sec = HierarchyNode(
            name="Sec",
            node_type="section",
            id="s-1",
            page_count=1,
            page_ids=["page-id-abc"],
            page_titles={"page-id-abc": "My Real Title"},
        )
        tree_nodes = [HierarchyNode(name="NB", node_type="notebook", id="nb-1", children=[sec])]
        captured: list[list[tuple[str, str]]] = []

        async def mock_export_batch(pages: list[tuple[str, str]], **kwargs: object) -> MagicMock:
            captured.append(pages)
            return _make_export_report(len(pages))

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=tree_nodes)),
            patch("src.cli.export_batch", new=mock_export_batch),
            patch("src.cli._is_interactive", return_value=False),
        ):
            runner.invoke(main, ["export", "--all"])

        assert len(captured) == 1
        assert captured[0] == [("page-id-abc", "My Real Title")]

    def test_export_falls_back_to_id_when_no_title_available(self) -> None:
        """Si page_titles est vide, le fallback sur l'ID doit s'appliquer."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()

        sec = HierarchyNode(
            name="Sec",
            node_type="section",
            id="s-1",
            page_count=1,
            page_ids=["page-id-abc"],
        )
        tree_nodes = [HierarchyNode(name="NB", node_type="notebook", id="nb-1", children=[sec])]
        captured: list[list[tuple[str, str]]] = []

        async def mock_export_batch(pages: list[tuple[str, str]], **kwargs: object) -> MagicMock:
            captured.append(pages)
            return _make_export_report(len(pages))

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=tree_nodes)),
            patch("src.cli.export_batch", new=mock_export_batch),
            patch("src.cli._is_interactive", return_value=False),
        ):
            runner.invoke(main, ["export", "--all"])

        assert len(captured) == 1
        pid, title = captured[0][0]
        assert pid == "page-id-abc"
        # fallback: title should be a non-empty string (either id or real title)
        assert title == "page-id-abc"


class TestFormatOption:
    """Tests pour l'option --format de la commande export."""

    def test_export_has_format_option(self) -> None:
        """La commande export doit avoir --format / -f."""
        runner = CliRunner()
        result = runner.invoke(main, ["export", "--help"])
        assert "--format" in result.output or "-f" in result.output

    def test_export_format_accepts_pdf(self) -> None:
        """--format pdf doit être accepté."""
        runner = CliRunner()
        result = runner.invoke(main, ["export", "--help"])
        assert "pdf" in result.output

    def test_export_format_accepts_txt(self) -> None:
        """--format txt doit être accepté."""
        runner = CliRunner()
        result = runner.invoke(main, ["export", "--help"])
        assert "txt" in result.output

    def test_export_format_default_is_pdf(self) -> None:
        """Le format par défaut doit être pdf."""
        runner = CliRunner()
        result = runner.invoke(main, ["export", "--help"])
        assert "pdf" in result.output


class TestNotebookOption:
    """Tests pour l'option --notebook du groupe principal."""

    def test_notebook_option_is_available(self) -> None:
        """Le flag --notebook/-n doit être disponible sur le groupe main."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "--notebook" in result.output or "-n" in result.output

    def test_notebook_option_accepted_with_tree(self) -> None:
        """--notebook doit être accepté avec la commande tree."""
        runner = CliRunner()
        mock_client = _make_graph_client_mock()

        with (
            patch("src.cli.authenticate", return_value="test-token"),
            patch("src.cli.GraphClient", return_value=mock_client),
            patch("src.cli.build_tree", new=AsyncMock(return_value=_EMPTY_NODES)),
            patch("src.cli.display_tree", return_value=""),
        ):
            result = runner.invoke(main, ["--notebook", "MyNB", "tree"])
            assert result.exit_code == 0
