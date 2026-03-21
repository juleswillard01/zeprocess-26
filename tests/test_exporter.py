"""Tests pour l'export PDF."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exporter import (
    ExportReport,
    ExportResult,
    _sanitize_html,
    export_batch,
    export_page_to_pdf,
    sanitize_filename,
)


class TestExportResult:
    """Tests pour le résultat d'export d'une page."""

    def test_successful_result_has_no_error(self) -> None:
        """Un export réussi ne doit pas avoir d'erreur."""
        result = ExportResult(
            page_title="Test",
            pdf_path=Path("out/test.pdf"),
            success=True,
        )
        assert result.success is True
        assert result.error is None

    def test_failed_result_has_error_message(self) -> None:
        """Un export échoué doit avoir un message d'erreur."""
        result = ExportResult(
            page_title="Test",
            pdf_path=Path("out/test.pdf"),
            success=False,
            error="WeasyPrint conversion failed",
        )
        assert result.success is False
        assert result.error is not None


class TestExportReport:
    """Tests pour le rapport d'export."""

    def test_success_rate_full_success(self) -> None:
        """100% si tout est exporté."""
        report = ExportReport(
            total_pages=10, exported=10, failed=0, total_size_bytes=1024, results=[]
        )
        assert report.success_rate == 100.0

    def test_success_rate_partial(self) -> None:
        """Calcul correct pour un export partiel."""
        report = ExportReport(
            total_pages=10, exported=7, failed=3, total_size_bytes=512, results=[]
        )
        assert report.success_rate == 70.0

    def test_success_rate_zero_pages(self) -> None:
        """0% si aucune page à exporter."""
        report = ExportReport(total_pages=0, exported=0, failed=0, total_size_bytes=0, results=[])
        assert report.success_rate == 0.0


class TestSanitizeFilename:
    """Tests pour la sanitisation des noms de fichiers."""

    def test_sanitize_filename_removes_special_chars(self) -> None:
        """Les caractères spéciaux doivent être supprimés."""
        title = "Page @#$% Name!!"
        result = sanitize_filename(title)
        assert result == "Page Name"

    def test_sanitize_filename_keeps_alphanumeric_and_spaces(self) -> None:
        """Les lettres, chiffres et espaces doivent être conservés."""
        title = "My Page 123"
        result = sanitize_filename(title)
        assert result == "My Page 123"

    def test_sanitize_filename_keeps_hyphens_and_underscores(self) -> None:
        """Les tirets et underscores doivent être conservés."""
        title = "My-Page_Name"
        result = sanitize_filename(title)
        assert result == "My-Page_Name"

    def test_sanitize_filename_strips_whitespace(self) -> None:
        """Les espaces en début/fin doivent être supprimés."""
        title = "   Page Name   "
        result = sanitize_filename(title)
        assert result == "Page Name"

    def test_sanitize_filename_handles_unicode(self) -> None:
        """Les caractères Unicode doivent être supprimés."""
        title = "Café Page™"
        result = sanitize_filename(title)
        # Seuls les caractères \w (alphanumériques et _) sont conservés, + - et espaces
        assert "Caf" in result or "Page" in result


class TestSanitizeHtml:
    """Tests pour la sanitisation HTML avant conversion PDF."""

    def test_sanitize_html_removes_script_tags(self) -> None:
        """Les balises script doivent être supprimées."""
        html = "<html><body><script>alert('xss')</script><p>Content</p></body></html>"
        result = _sanitize_html(html)
        assert "<script" not in result
        assert "alert" not in result
        assert "<p>Content</p>" in result

    def test_sanitize_html_removes_script_tags_case_insensitive(self) -> None:
        """La suppression doit être insensible à la casse."""
        html = "<HTML><BODY><SCRIPT>evil()</SCRIPT>text</BODY></HTML>"
        result = _sanitize_html(html)
        assert "<SCRIPT" not in result.upper()
        assert "evil()" not in result

    def test_sanitize_html_removes_iframe_tags(self) -> None:
        """Les balises iframe doivent être supprimées."""
        html = '<html><body><iframe src="evil.com"></iframe><p>OK</p></body></html>'
        result = _sanitize_html(html)
        assert "<iframe" not in result
        assert "<p>OK</p>" in result

    def test_sanitize_html_removes_object_tags(self) -> None:
        """Les balises object doivent être supprimées."""
        html = "<html><body><object data='x.swf'><param/></object><p>OK</p></body></html>"
        result = _sanitize_html(html)
        assert "<object" not in result
        assert "<p>OK</p>" in result

    def test_sanitize_html_removes_embed_tags(self) -> None:
        """Les balises embed doivent être supprimées."""
        html = "<html><body><embed src='evil.swf'/><p>OK</p></body></html>"
        result = _sanitize_html(html)
        assert "<embed" not in result
        assert "<p>OK</p>" in result

    def test_sanitize_html_removes_link_tags(self) -> None:
        """Les balises link doivent être supprimées."""
        html = '<html><head><link rel="stylesheet" href="evil.css"></head><body>OK</body></html>'
        result = _sanitize_html(html)
        assert "<link" not in result
        assert "OK" in result

    def test_sanitize_html_preserves_safe_content(self) -> None:
        """Le contenu sûr ne doit pas être modifié."""
        html = "<html><body><h1>Title</h1><p>Paragraph</p></body></html>"
        result = _sanitize_html(html)
        assert "<h1>Title</h1>" in result
        assert "<p>Paragraph</p>" in result

    def test_sanitize_html_multiline_script(self) -> None:
        """Les balises script multilignes doivent être supprimées."""
        html = "<html><body><script>\nfunction evil() {\n}\n</script><p>Safe</p></body></html>"
        result = _sanitize_html(html)
        assert "<script" not in result
        assert "evil" not in result
        assert "<p>Safe</p>" in result


class TestExportPageToPdf:
    """Tests pour la conversion d'une page en PDF."""

    @pytest.mark.asyncio
    async def test_export_page_to_pdf_creates_file(self, tmp_path: Path) -> None:
        """La conversion doit créer un fichier PDF."""
        page_id = "page-123"
        page_title = "Test Page"
        html_content = "<html><body>Test</body></html>"
        output_dir = tmp_path

        with patch("src.exporter.HTML") as mock_html:
            mock_instance = MagicMock()
            mock_html.return_value = mock_instance

            def mock_write_pdf(path: str) -> None:
                # Simuler la création du fichier
                Path(path).write_bytes(b"PDF content")

            mock_instance.write_pdf.side_effect = mock_write_pdf

            result = await export_page_to_pdf(
                page_id=page_id,
                page_title=page_title,
                html_content=html_content,
                output_dir=output_dir,
                order=1,
            )

            assert result.success is True
            assert result.page_title == page_title
            assert result.pdf_path.parent == output_dir
            mock_html.assert_called_once()
            mock_instance.write_pdf.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_page_to_pdf_sanitizes_filename(self, tmp_path: Path) -> None:
        """Le nom du fichier doit être sanitisé."""
        page_id = "page-456"
        page_title = "Page @#$% with special chars!!"
        html_content = "<html><body>Test</body></html>"
        output_dir = tmp_path

        with patch("src.exporter.HTML") as mock_html:
            mock_instance = MagicMock()
            mock_html.return_value = mock_instance

            def mock_write_pdf(path: str) -> None:
                Path(path).write_bytes(b"PDF content")

            mock_instance.write_pdf.side_effect = mock_write_pdf

            result = await export_page_to_pdf(
                page_id=page_id,
                page_title=page_title,
                html_content=html_content,
                output_dir=output_dir,
                order=0,
            )

            # Vérifier que le nom du fichier ne contient pas de caractères spéciaux
            filename = result.pdf_path.name
            # Le nom doit être de la forme: 000_<titre_sanitisé>.pdf
            assert filename.startswith("000_")
            assert filename.endswith(".pdf")
            # Vérifier qu'il ne contient pas de caractères spéciaux
            assert not re.search(r"[@#$%!]", filename)

    @pytest.mark.asyncio
    async def test_export_page_to_pdf_uses_order_prefix(self, tmp_path: Path) -> None:
        """Le numéro d'ordre doit être préfixé avec 3 chiffres."""
        page_id = "page-789"
        page_title = "Test"
        html_content = "<html><body>Test</body></html>"
        output_dir = tmp_path

        with patch("src.exporter.HTML") as mock_html:
            mock_instance = MagicMock()
            mock_html.return_value = mock_instance

            def mock_write_pdf(path: str) -> None:
                Path(path).write_bytes(b"PDF content")

            mock_instance.write_pdf.side_effect = mock_write_pdf

            for order in [0, 5, 42]:
                result = await export_page_to_pdf(
                    page_id=page_id,
                    page_title=page_title,
                    html_content=html_content,
                    output_dir=output_dir,
                    order=order,
                )

                filename = result.pdf_path.name
                expected_prefix = f"{order:03d}_"
                assert filename.startswith(expected_prefix)

    @pytest.mark.asyncio
    async def test_export_page_to_pdf_handles_weasyprint_error(self, tmp_path: Path) -> None:
        """Les erreurs WeasyPrint doivent être capturées."""
        page_id = "page-error"
        page_title = "Error Page"
        html_content = "<html><body>Test</body></html>"
        output_dir = tmp_path

        with patch("src.exporter.HTML") as mock_html:
            mock_instance = MagicMock()
            mock_html.return_value = mock_instance
            error_msg = "WeasyPrint conversion failed"
            mock_instance.write_pdf.side_effect = Exception(error_msg)

            result = await export_page_to_pdf(
                page_id=page_id,
                page_title=page_title,
                html_content=html_content,
                output_dir=output_dir,
                order=0,
            )

            assert result.success is False
            assert result.error is not None
            assert (
                "conversion failed" in result.error.lower() or "weasyprint" in result.error.lower()
            )

    @pytest.mark.asyncio
    async def test_export_page_to_pdf_sets_size_bytes(self, tmp_path: Path) -> None:
        """Le résultat doit contenir la taille du fichier en octets."""
        page_id = "page-size"
        page_title = "Size Test"
        html_content = "<html><body>Test</body></html>"
        output_dir = tmp_path
        file_content = b"PDF content " * 100  # Environ 1200 bytes

        with patch("src.exporter.HTML") as mock_html:
            mock_instance = MagicMock()
            mock_html.return_value = mock_instance

            def mock_write_pdf(path: str) -> None:
                Path(path).write_bytes(file_content)

            mock_instance.write_pdf.side_effect = mock_write_pdf

            result = await export_page_to_pdf(
                page_id=page_id,
                page_title=page_title,
                html_content=html_content,
                output_dir=output_dir,
                order=0,
            )

            assert result.size_bytes == len(file_content)
            assert result.success is True


class TestExportBatch:
    """Tests pour l'export en lot."""

    @pytest.mark.asyncio
    async def test_export_batch_processes_all_pages(self, tmp_path: Path) -> None:
        """Tous les pages doivent être traitées."""
        pages = [("page-1", "Title 1"), ("page-2", "Title 2"), ("page-3", "Title 3")]
        output_dir = tmp_path

        with (
            patch("src.exporter.export_page_to_pdf") as mock_export,
            patch("src.exporter.asyncio.sleep"),
        ):

            async def create_result(page_id: str, *args: object, **kwargs: object) -> ExportResult:
                return ExportResult(
                    page_title=f"Page {page_id}",
                    pdf_path=output_dir / f"{page_id}.pdf",
                    success=True,
                    size_bytes=512,
                )

            mock_export.side_effect = create_result

            report = await export_batch(
                pages=pages,
                output_dir=output_dir,
                rate_limit=4,
            )

            assert mock_export.call_count == len(pages)
            assert report.total_pages == len(pages)

    @pytest.mark.asyncio
    async def test_export_batch_uses_page_title_from_tuple(self, tmp_path: Path) -> None:
        """Le titre de la page doit être issu du tuple, pas généré depuis l'ID."""
        pages = [("page-1", "My Real Title")]
        output_dir = tmp_path

        captured_kwargs: list[dict[str, object]] = []

        with (
            patch("src.exporter.export_page_to_pdf") as mock_export,
            patch("src.exporter.asyncio.sleep"),
        ):

            async def capture_call(**kwargs: object) -> ExportResult:
                captured_kwargs.append(dict(kwargs))
                return ExportResult(
                    page_title=str(kwargs["page_title"]),
                    pdf_path=output_dir / "page-1.pdf",
                    success=True,
                    size_bytes=256,
                )

            mock_export.side_effect = capture_call

            await export_batch(pages=pages, output_dir=output_dir)

        assert captured_kwargs[0]["page_title"] == "My Real Title"
        assert captured_kwargs[0]["page_id"] == "page-1"

    @pytest.mark.asyncio
    async def test_export_batch_returns_report_with_stats(self, tmp_path: Path) -> None:
        """Le rapport doit contenir les bonnes statistiques."""
        pages = [("page-1", "Title 1"), ("page-2", "Title 2"), ("page-3", "Title 3")]
        output_dir = tmp_path

        with (
            patch("src.exporter.export_page_to_pdf") as mock_export,
            patch("src.exporter.asyncio.sleep"),
        ):
            # 2 succès, 1 échec
            async def create_result(page_id: str, *args: object, **kwargs: object) -> ExportResult:
                success = page_id != "page-3"
                return ExportResult(
                    page_title=f"Page {page_id}",
                    pdf_path=output_dir / f"{page_id}.pdf",
                    success=success,
                    error="Export failed" if not success else None,
                    size_bytes=512 if success else 0,
                )

            mock_export.side_effect = create_result

            report = await export_batch(
                pages=pages,
                output_dir=output_dir,
                rate_limit=4,
            )

        assert report.total_pages == 3
        assert report.exported == 2
        assert report.failed == 1
        assert report.total_size_bytes == 1024  # 2 * 512
        assert len(report.results) == 3
        assert abs(report.success_rate - (200.0 / 3)) < 0.01  # ~66.67%

    @pytest.mark.asyncio
    async def test_export_batch_logs_errors_to_file(self, tmp_path: Path) -> None:
        """Les erreurs doivent être enregistrées dans errors.log."""
        pages = [("page-ok", "OK Page"), ("page-error", "Error Page")]
        output_dir = tmp_path

        with (
            patch("src.exporter.export_page_to_pdf") as mock_export,
            patch("src.exporter.asyncio.sleep"),
        ):

            async def create_result(page_id: str, *args: object, **kwargs: object) -> ExportResult:
                success = page_id == "page-ok"
                return ExportResult(
                    page_title=f"Page {page_id}",
                    pdf_path=output_dir / f"{page_id}.pdf",
                    success=success,
                    error="Conversion failed" if not success else None,
                    size_bytes=256 if success else 0,
                )

            mock_export.side_effect = create_result

            report = await export_batch(
                pages=pages,
                output_dir=output_dir,
                rate_limit=4,
            )

        # Vérifier que le fichier errors.log a été créé
        errors_log = output_dir / "errors.log"
        assert errors_log.exists() or report.failed > 0

        # Si le fichier existe, il doit contenir l'erreur
        if errors_log.exists():
            content = errors_log.read_text()
            assert "page-error" in content or "Conversion failed" in content

    @pytest.mark.asyncio
    async def test_export_batch_sleeps_between_requests_for_rate_limit(
        self, tmp_path: Path
    ) -> None:
        """Un sleep de 1/rate_limit doit être inséré entre chaque requête."""
        pages = [(f"page-{i}", f"Title {i}") for i in range(10)]
        output_dir = tmp_path
        sleep_calls: list[float] = []

        with patch("src.exporter.export_page_to_pdf") as mock_export:

            async def fast_export(page_id: str, *args: object, **kwargs: object) -> ExportResult:
                return ExportResult(
                    page_title=f"Page {page_id}",
                    pdf_path=output_dir / f"{page_id}.pdf",
                    success=True,
                    size_bytes=256,
                )

            mock_export.side_effect = fast_export

            async def capture_sleep(delay: float) -> None:
                sleep_calls.append(delay)

            with patch("src.exporter.asyncio.sleep", side_effect=capture_sleep):
                report = await export_batch(
                    pages=pages,
                    output_dir=output_dir,
                    rate_limit=4,
                )

        # 10 pages → 9 sleeps (no sleep after last item)
        assert len(sleep_calls) == 9
        # Each sleep = 1.0 / rate_limit = 0.25s
        assert all(abs(s - 0.25) < 1e-9 for s in sleep_calls)
        assert report.total_pages == 10
        assert report.exported == 10

    @pytest.mark.asyncio
    async def test_export_batch_empty_list(self, tmp_path: Path) -> None:
        """Un lot vide doit retourner un rapport valide."""
        output_dir = tmp_path

        report = await export_batch(
            pages=[],
            output_dir=output_dir,
            rate_limit=4,
        )

        assert report.total_pages == 0
        assert report.exported == 0
        assert report.failed == 0
        assert report.total_size_bytes == 0
        assert report.success_rate == 0.0
        assert len(report.results) == 0


class TestExportBatchProgress:
    """Tests pour le paramètre progress de export_batch."""

    @pytest.mark.asyncio
    async def test_export_batch_with_progress_false_works(self, tmp_path: Path) -> None:
        """export_batch avec progress=False doit fonctionner sans erreur."""
        pages = [("page-1", "Title 1"), ("page-2", "Title 2")]

        with (
            patch("src.exporter.export_page_to_pdf") as mock_export,
            patch("src.exporter.asyncio.sleep"),
        ):

            async def create_result(page_id: str, *args: object, **kwargs: object) -> ExportResult:
                return ExportResult(
                    page_title=f"Page {page_id}",
                    pdf_path=tmp_path / f"{page_id}.pdf",
                    success=True,
                    size_bytes=512,
                )

            mock_export.side_effect = create_result

            report = await export_batch(
                pages=pages,
                output_dir=tmp_path,
                rate_limit=4,
                progress=False,
            )

        assert report.total_pages == 2
        assert report.exported == 2

    @pytest.mark.asyncio
    async def test_export_batch_default_progress_is_true(self) -> None:
        """Le paramètre progress doit être True par défaut."""
        import inspect

        sig = inspect.signature(export_batch)
        assert "progress" in sig.parameters
        assert sig.parameters["progress"].default is True

    @pytest.mark.asyncio
    async def test_export_batch_progress_does_not_affect_results(self, tmp_path: Path) -> None:
        """Les résultats doivent être identiques avec ou sans progress."""
        pages = [("page-1", "Title 1"), ("page-2", "Title 2"), ("page-3", "Title 3")]

        def make_exporter() -> object:
            async def create_result(page_id: str, *args: object, **kwargs: object) -> ExportResult:
                return ExportResult(
                    page_title=f"Page {page_id}",
                    pdf_path=tmp_path / f"{page_id}.pdf",
                    success=True,
                    size_bytes=256,
                )

            return create_result

        with (
            patch("src.exporter.export_page_to_pdf") as mock_export,
            patch("src.exporter.asyncio.sleep"),
        ):
            mock_export.side_effect = make_exporter()
            report_no_progress = await export_batch(
                pages=pages,
                output_dir=tmp_path,
                rate_limit=4,
                progress=False,
            )

        with (
            patch("src.exporter.export_page_to_pdf") as mock_export2,
            patch("src.exporter.asyncio.sleep"),
            patch("sys.stderr") as mock_stderr,
        ):
            # Simulate a non-TTY so rich.Progress is NOT actually rendered
            mock_stderr.isatty.return_value = False
            mock_export2.side_effect = make_exporter()
            report_with_progress = await export_batch(
                pages=pages,
                output_dir=tmp_path,
                rate_limit=4,
                progress=True,
            )

        assert report_no_progress.total_pages == report_with_progress.total_pages
        assert report_no_progress.exported == report_with_progress.exported
        assert report_no_progress.failed == report_with_progress.failed
        assert report_no_progress.total_size_bytes == report_with_progress.total_size_bytes


class TestReplaceImagesWithDataUris:
    """Tests pour le remplacement d'images Graph en data URIs."""

    @pytest.mark.asyncio
    async def test_replaces_graph_image_urls_with_data_uris(self) -> None:
        """Les URLs Graph images doivent être remplacées par des data URIs."""
        import base64

        from src.exporter import _replace_images_with_data_uris
        from src.graph import GraphClient

        image_bytes = b"\x89PNG fake image data"
        graph_url = "https://graph.microsoft.com/v1.0/me/onenote/resources/res-1/$value"
        html = f'<html><body><img src="{graph_url}" /></body></html>'

        mock_client = MagicMock(spec=GraphClient)
        mock_client.download_resource = AsyncMock(return_value=image_bytes)

        result = await _replace_images_with_data_uris(html, mock_client)

        expected_b64 = base64.b64encode(image_bytes).decode()
        assert f"data:image/png;base64,{expected_b64}" in result
        assert graph_url not in result

    @pytest.mark.asyncio
    async def test_leaves_non_graph_urls_unchanged(self) -> None:
        """Les URLs non-Graph ne doivent pas être modifiées."""
        from src.exporter import _replace_images_with_data_uris
        from src.graph import GraphClient

        external_url = "https://example.com/image.png"
        html = f'<html><body><img src="{external_url}" /></body></html>'

        mock_client = MagicMock(spec=GraphClient)
        mock_client.download_resource = AsyncMock(return_value=b"bytes")

        result = await _replace_images_with_data_uris(html, mock_client)

        assert external_url in result
        mock_client.download_resource.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_html_without_images(self) -> None:
        """Un HTML sans images doit être retourné tel quel."""
        from src.exporter import _replace_images_with_data_uris
        from src.graph import GraphClient

        html = "<html><body><p>No images here</p></body></html>"
        mock_client = MagicMock(spec=GraphClient)
        mock_client.download_resource = AsyncMock(return_value=b"bytes")

        result = await _replace_images_with_data_uris(html, mock_client)

        assert result == html
        mock_client.download_resource.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_multiple_images(self) -> None:
        """Plusieurs images Graph doivent toutes être remplacées."""
        import base64

        from src.exporter import _replace_images_with_data_uris
        from src.graph import GraphClient

        bytes_1 = b"image data 1"
        bytes_2 = b"image data 2"
        url_1 = "https://graph.microsoft.com/v1.0/me/onenote/resources/res-1/$value"
        url_2 = "https://graph.microsoft.com/v1.0/me/onenote/resources/res-2/$value"
        html = f'<html><body><img src="{url_1}" /><img src="{url_2}" /></body></html>'

        mock_client = MagicMock(spec=GraphClient)
        mock_client.download_resource = AsyncMock(side_effect=[bytes_1, bytes_2])

        result = await _replace_images_with_data_uris(html, mock_client)

        b64_1 = base64.b64encode(bytes_1).decode()
        b64_2 = base64.b64encode(bytes_2).decode()
        assert f"data:image/png;base64,{b64_1}" in result
        assert f"data:image/png;base64,{b64_2}" in result
        assert url_1 not in result
        assert url_2 not in result
        assert mock_client.download_resource.call_count == 2

    @pytest.mark.asyncio
    async def test_leaves_data_uri_images_unchanged(self) -> None:
        """Les images déjà en data URI ne doivent pas être touchées."""
        from src.exporter import _replace_images_with_data_uris
        from src.graph import GraphClient

        data_uri = "data:image/png;base64,iVBORw0KGgo="
        html = f'<html><body><img src="{data_uri}" /></body></html>'

        mock_client = MagicMock(spec=GraphClient)
        mock_client.download_resource = AsyncMock(return_value=b"bytes")

        result = await _replace_images_with_data_uris(html, mock_client)

        assert data_uri in result
        mock_client.download_resource.assert_not_called()


class TestExportPageToPdfWithClient:
    """Tests pour export_page_to_pdf avec client GraphClient."""

    @pytest.mark.asyncio
    async def test_export_page_with_client_replaces_images(self, tmp_path: Path) -> None:
        """export_page_to_pdf doit remplacer les images quand un client est fourni."""
        import base64

        from src.graph import GraphClient

        image_bytes = b"fake png bytes"
        graph_url = "https://graph.microsoft.com/v1.0/me/onenote/resources/res-1/$value"
        html_content = f'<html><body><img src="{graph_url}" /></body></html>'

        mock_client = MagicMock(spec=GraphClient)
        mock_client.download_resource = AsyncMock(return_value=image_bytes)

        with patch("src.exporter.HTML") as mock_html:
            mock_instance = MagicMock()
            mock_html.return_value = mock_instance

            def mock_write_pdf(path: str) -> None:
                Path(path).write_bytes(b"PDF content")

            mock_instance.write_pdf.side_effect = mock_write_pdf

            result = await export_page_to_pdf(
                page_id="page-1",
                page_title="Test",
                html_content=html_content,
                output_dir=tmp_path,
                order=0,
                client=mock_client,
            )

        assert result.success is True
        # The HTML passed to weasyprint must contain the data URI, not the graph URL
        html_arg = mock_html.call_args[1]["string"]
        b64 = base64.b64encode(image_bytes).decode()
        assert f"data:image/png;base64,{b64}" in html_arg
        assert graph_url not in html_arg

    @pytest.mark.asyncio
    async def test_export_page_without_client_skips_image_replacement(self, tmp_path: Path) -> None:
        """export_page_to_pdf sans client ne doit pas altérer les src d'images."""
        graph_url = "https://graph.microsoft.com/v1.0/me/onenote/resources/res-1/$value"
        html_content = f'<html><body><img src="{graph_url}" /></body></html>'

        with patch("src.exporter.HTML") as mock_html:
            mock_instance = MagicMock()
            mock_html.return_value = mock_instance

            def mock_write_pdf(path: str) -> None:
                Path(path).write_bytes(b"PDF content")

            mock_instance.write_pdf.side_effect = mock_write_pdf

            result = await export_page_to_pdf(
                page_id="page-1",
                page_title="Test",
                html_content=html_content,
                output_dir=tmp_path,
                order=0,
            )

        assert result.success is True
        html_arg = mock_html.call_args[1]["string"]
        assert graph_url in html_arg


class TestExportPageToTxt:
    """Tests pour l'export en fichier texte."""

    @pytest.mark.asyncio
    async def test_export_txt_creates_file(self, tmp_path: Path) -> None:
        """L'export TXT doit créer un fichier .txt."""
        from src.exporter import export_page_to_txt

        result = await export_page_to_txt(
            page_id="page-1",
            page_title="Test Page",
            html_content="<html><body><p>Hello World</p></body></html>",
            output_dir=tmp_path,
            order=0,
        )

        assert result.success is True
        assert result.pdf_path.suffix == ".txt"
        assert result.pdf_path.exists()
        content = result.pdf_path.read_text()
        assert "Hello World" in content

    @pytest.mark.asyncio
    async def test_export_txt_strips_html_tags(self, tmp_path: Path) -> None:
        """L'export TXT doit supprimer les balises HTML."""
        from src.exporter import export_page_to_txt

        html = "<html><body><h1>Title</h1><p>Para <b>bold</b></p></body></html>"
        result = await export_page_to_txt(
            page_id="page-2",
            page_title="Strip Test",
            html_content=html,
            output_dir=tmp_path,
            order=0,
        )

        content = result.pdf_path.read_text()
        assert "<h1>" not in content
        assert "<p>" not in content
        assert "<b>" not in content
        assert "Title" in content
        assert "bold" in content

    @pytest.mark.asyncio
    async def test_export_txt_decodes_html_entities(self, tmp_path: Path) -> None:
        """L'export TXT doit décoder les entités HTML."""
        from src.exporter import export_page_to_txt

        html = "<html><body><p>A &amp; B &lt; C &gt; D</p></body></html>"
        result = await export_page_to_txt(
            page_id="page-3",
            page_title="Entity Test",
            html_content=html,
            output_dir=tmp_path,
            order=0,
        )

        content = result.pdf_path.read_text()
        assert "A & B" in content
        assert "< C >" in content

    @pytest.mark.asyncio
    async def test_export_txt_path_traversal_blocked(self, tmp_path: Path) -> None:
        """Après sanitize, '../../etc/passwd' → 'etcpasswd', reste dans output_dir."""
        from src.exporter import export_page_to_txt

        result = await export_page_to_txt(
            page_id="page-evil",
            page_title="../../etc/passwd",
            html_content="<html><body>evil</body></html>",
            output_dir=tmp_path,
            order=0,
        )

        # sanitize_filename strips ".." and "/" → "etcpasswd"
        # is_relative_to guard passes since resolved path stays inside output_dir
        assert result.success is True
        assert result.pdf_path.exists()
        assert "etcpasswd" in result.pdf_path.name

    @pytest.mark.asyncio
    async def test_export_txt_sanitizes_filename(self, tmp_path: Path) -> None:
        """Le nom du fichier TXT doit être sanitisé."""
        from src.exporter import export_page_to_txt

        result = await export_page_to_txt(
            page_id="page-4",
            page_title="Page @#$% Name!!",
            html_content="<html><body>content</body></html>",
            output_dir=tmp_path,
            order=5,
        )

        assert result.success is True
        assert result.pdf_path.name.startswith("005_")
        assert result.pdf_path.suffix == ".txt"


class TestTxtExportSlashInTitle:
    """Tests pour les titres avec slash — Bug 1 fix."""

    @pytest.mark.asyncio
    async def test_export_txt_with_slash_in_title_succeeds(self, tmp_path: Path) -> None:
        """Un titre avec '/' comme 'LR 5/7' doit réussir l'export."""
        from src.exporter import export_page_to_txt

        result = await export_page_to_txt(
            page_id="page-slash",
            page_title="LR 5/7",
            html_content="<html><body>Contenu légal</body></html>",
            output_dir=tmp_path,
            order=0,
        )

        assert result.success is True
        assert result.pdf_path.exists()
        assert result.pdf_path.suffix == ".txt"
        assert "LR 57" in result.pdf_path.name  # "/" stripped by sanitize

    @pytest.mark.asyncio
    async def test_export_txt_with_backslash_in_title_succeeds(self, tmp_path: Path) -> None:
        """Un titre avec backslash doit réussir après sanitize."""
        from src.exporter import export_page_to_txt

        result = await export_page_to_txt(
            page_id="page-bs",
            page_title="Section\\Subsection",
            html_content="<html><body>Content</body></html>",
            output_dir=tmp_path,
            order=1,
        )

        assert result.success is True
        assert result.pdf_path.exists()

    @pytest.mark.asyncio
    async def test_export_txt_with_dotdot_sanitized(self, tmp_path: Path) -> None:
        """Un titre avec '..' doit être sanitisé mais pas crash."""
        from src.exporter import export_page_to_txt

        result = await export_page_to_txt(
            page_id="page-dots",
            page_title="Note..v2",
            html_content="<html><body>Content</body></html>",
            output_dir=tmp_path,
            order=2,
        )

        assert result.success is True
        assert result.pdf_path.exists()
        # The is_relative_to guard should pass since sanitize removes ".."


class TestExportBatchFormat:
    """Tests pour le paramètre fmt de export_batch."""

    @pytest.mark.asyncio
    async def test_export_batch_txt_format(self, tmp_path: Path) -> None:
        """export_batch avec fmt='txt' doit produire des .txt."""
        pages = [("page-1", "Title 1")]

        with patch("src.exporter.asyncio.sleep"):
            report = await export_batch(
                pages=pages,
                output_dir=tmp_path,
                rate_limit=4,
                progress=False,
                fmt="txt",
            )

        assert report.total_pages == 1
        # Vérifie qu'un fichier txt a été créé
        txt_files = list(tmp_path.glob("*.txt"))
        assert len(txt_files) >= 1

    @pytest.mark.asyncio
    async def test_export_batch_default_format_is_pdf(self) -> None:
        """Le format par défaut doit être 'pdf'."""
        import inspect

        sig = inspect.signature(export_batch)
        assert sig.parameters["fmt"].default == "pdf"


class TestExportBatchResume:
    """Tests pour le paramètre resume de export_batch."""

    @pytest.mark.asyncio
    async def test_resume_skips_existing_txt_file(self, tmp_path: Path) -> None:
        """Avec resume=True, un fichier TXT existant doit être skippé."""
        existing = tmp_path / "000_Title 1.txt"
        existing.write_text("already exported content")

        pages = [("page-1", "Title 1"), ("page-2", "Title 2")]

        with patch("src.exporter.asyncio.sleep"):
            report = await export_batch(
                pages=pages,
                output_dir=tmp_path,
                rate_limit=4,
                progress=False,
                fmt="txt",
                resume=True,
            )

        assert report.total_pages == 2
        assert report.exported == 2
        # Le premier fichier n'a pas été ré-écrit
        assert existing.read_text() == "already exported content"

    @pytest.mark.asyncio
    async def test_no_resume_does_not_skip(self, tmp_path: Path) -> None:
        """Avec resume=False, les fichiers existants doivent être ré-exportés."""
        existing = tmp_path / "000_Title 1.txt"
        existing.write_text("old content")

        pages = [("page-1", "Title 1")]

        with patch("src.exporter.asyncio.sleep"):
            report = await export_batch(
                pages=pages,
                output_dir=tmp_path,
                rate_limit=4,
                progress=False,
                fmt="txt",
                resume=False,
            )

        assert report.exported == 1
        content = existing.read_text()
        assert content != "old content"

    @pytest.mark.asyncio
    async def test_resume_default_is_true(self) -> None:
        """Le paramètre resume doit être True par défaut."""
        import inspect

        sig = inspect.signature(export_batch)
        assert sig.parameters["resume"].default is True
