"""Export de pages OneNote en PDF ou TXT via HTML intermédiaire."""

from __future__ import annotations

import asyncio
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING

from rich.progress import Progress
from weasyprint import HTML

if TYPE_CHECKING:
    from src.graph import GraphClient

logger = logging.getLogger(__name__)


@dataclass
class ExportResult:
    """Résultat d'un export de page."""

    page_title: str
    pdf_path: Path
    success: bool
    error: str | None = None
    size_bytes: int = 0


@dataclass
class ExportReport:
    """Rapport global d'un batch d'export."""

    total_pages: int
    exported: int
    failed: int
    total_size_bytes: int
    results: list[ExportResult]

    @property
    def success_rate(self) -> float:
        """Taux de succès en pourcentage."""
        if self.total_pages == 0:
            return 0.0
        return (self.exported / self.total_pages) * 100.0


def sanitize_filename(title: str) -> str:
    """Sanitise un titre pour en faire un nom de fichier valide.

    Args:
        title: Titre original.

    Returns:
        Titre nettoyé sans caractères spéciaux.
    """
    sanitized = re.sub(r"[^\w\s-]", "", title)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized


def _sanitize_html(html: str) -> str:
    """Remove script, iframe, object, embed and link tags from HTML content.

    Args:
        html: Raw HTML string from OneNote.

    Returns:
        HTML with dangerous tags stripped.
    """
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<iframe[^>]*>.*?</iframe>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<object[^>]*>.*?</object>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<embed[^>]*/?>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<link[^>]*>", "", html, flags=re.IGNORECASE)
    return html


async def _replace_images_with_data_uris(html: str, client: GraphClient) -> str:
    """Remplace les URLs d'images Graph par des data URIs base64.

    Args:
        html: Contenu HTML avec potentiellement des images Graph.
        client: Client Graph API pour télécharger les images.

    Returns:
        HTML avec les images Graph remplacées par des data URIs.
    """
    import base64

    graph_pattern = re.compile(
        r'(<img[^>]*\ssrc=")'
        r"(https://graph\.microsoft\.com/[^\"]+)"
        r'("[^>]*>)',
        re.IGNORECASE,
    )

    matches = list(graph_pattern.finditer(html))
    if not matches:
        return html

    result = html
    for match in reversed(matches):
        url = match.group(2)
        try:
            image_bytes = await client.download_resource(url)
            b64 = base64.b64encode(image_bytes).decode()
            data_uri = f"data:image/png;base64,{b64}"
            result = result[: match.start(2)] + data_uri + result[match.end(2) :]
        except Exception:
            logger.warning("Failed to download image: %s", url)

    return result


async def export_page_to_pdf(
    page_id: str,
    page_title: str,
    html_content: str,
    output_dir: Path,
    order: int = 0,
    client: GraphClient | None = None,
) -> ExportResult:
    """Convertit le contenu HTML d'une page OneNote en PDF.

    Args:
        page_id: ID de la page Graph API.
        page_title: Titre de la page pour le nommage du fichier.
        html_content: Contenu HTML de la page.
        output_dir: Dossier de destination.
        order: Numéro d'ordre pour le tri.
        client: Client Graph API pour remplacer les images embarquées.

    Returns:
        Résultat de l'export avec chemin du PDF.
    """
    try:
        if client is not None:
            html_content = await _replace_images_with_data_uris(html_content, client)

        safe_title = sanitize_filename(page_title)
        filename = f"{order:03d}_{safe_title}.pdf"
        pdf_path = output_dir / filename

        # Path traversal guard: resolved path must stay inside output_dir
        resolved_output = output_dir.resolve()
        resolved_pdf = pdf_path.resolve()
        if not resolved_pdf.is_relative_to(resolved_output):
            raise ValueError(f"Path traversal detected for page {page_id}")

        output_dir.mkdir(parents=True, exist_ok=True)

        sanitized_html = _sanitize_html(html_content)
        HTML(string=sanitized_html).write_pdf(str(pdf_path))  # type: ignore[no-untyped-call]

        size_bytes = pdf_path.stat().st_size

        return ExportResult(
            page_title=page_title,
            pdf_path=pdf_path,
            success=True,
            size_bytes=size_bytes,
        )
    except Exception as e:
        logger.error("Export failed for page %s: %s", page_id, e, exc_info=True)
        return ExportResult(
            page_title=page_title,
            pdf_path=output_dir / f"{order:03d}_error.pdf",
            success=False,
            error=str(e),
        )


def _html_to_plain_text(html: str) -> str:
    """Converts HTML to plain text by stripping tags and decoding entities.

    Args:
        html: Raw HTML string.

    Returns:
        Plain text with tags removed and HTML entities decoded.
    """
    import html as html_lib

    text = re.sub(r"<[^>]+>", "", html, flags=re.DOTALL)
    text = html_lib.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def export_page_to_txt(
    page_id: str,
    page_title: str,
    html_content: str,
    output_dir: Path,
    order: int = 0,
) -> ExportResult:
    """Converts a OneNote page HTML to a plain-text .txt file.

    Args:
        page_id: ID de la page Graph API.
        page_title: Titre de la page pour le nommage du fichier.
        html_content: Contenu HTML de la page.
        output_dir: Dossier de destination.
        order: Numéro d'ordre pour le tri.

    Returns:
        ExportResult with the path to the .txt file.
    """
    try:
        # Reject titles with path traversal sequences before any sanitization.
        if ".." in page_title or "/" in page_title or "\\" in page_title:
            raise ValueError(f"Path traversal detected for page {page_id}")

        safe_title = sanitize_filename(page_title)
        filename = f"{order:03d}_{safe_title}.txt"
        txt_path = output_dir / filename

        resolved_output = output_dir.resolve()
        resolved_txt = txt_path.resolve()
        if not resolved_txt.is_relative_to(resolved_output):
            raise ValueError(f"Path traversal detected for page {page_id}")

        output_dir.mkdir(parents=True, exist_ok=True)

        plain_text = _html_to_plain_text(html_content)
        txt_path.write_text(plain_text, encoding="utf-8")

        size_bytes = txt_path.stat().st_size

        return ExportResult(
            page_title=page_title,
            pdf_path=txt_path,
            success=True,
            size_bytes=size_bytes,
        )
    except Exception as e:
        logger.error("TXT export failed for page %s: %s", page_id, e, exc_info=True)
        return ExportResult(
            page_title=page_title,
            pdf_path=output_dir / f"{order:03d}_error.txt",
            success=False,
            error=str(e),
        )


async def _export_page(
    idx: int,
    page_id: str,
    page_title: str,
    client: GraphClient | None,
    output_dir: Path,
    rate_limit: int,
    pages_count: int,
    fmt: str = "pdf",
) -> ExportResult:
    """Helper: fetch content and convert one page, then sleep for rate limit.

    Args:
        idx: Zero-based index of this page in the batch.
        page_id: Graph API page ID.
        page_title: Human-readable page title.
        client: Graph API client; if None, uses empty HTML stub.
        output_dir: Destination directory.
        rate_limit: Max requests per second.
        pages_count: Total number of pages in the batch (used to skip final sleep).
        fmt: Output format — 'pdf' or 'txt'.

    Returns:
        ExportResult for the page.
    """
    if client is not None:
        html_content = await client.get_page_content(page_id)
    else:
        html_content = "<html><body></body></html>"

    if fmt == "txt":
        result = await export_page_to_txt(
            page_id=page_id,
            page_title=page_title,
            html_content=html_content,
            output_dir=output_dir,
            order=idx,
        )
    else:
        result = await export_page_to_pdf(
            page_id=page_id,
            page_title=page_title,
            html_content=html_content,
            output_dir=output_dir,
            order=idx,
            client=client,
        )

    if idx < pages_count - 1:
        await asyncio.sleep(1.0 / rate_limit)

    return result


async def export_batch(
    pages: list[tuple[str, str]],  # (page_id, page_title)
    client: GraphClient | None = None,
    output_dir: Path | None = None,
    rate_limit: int = 4,
    progress: bool = True,
    fmt: str = "pdf",
) -> ExportReport:
    """Exporte un lot de pages en respectant le rate limit.

    Args:
        pages: Liste de tuples (page_id, page_title) à exporter.
        client: Client Graph API pour récupérer le contenu des pages.
        output_dir: Dossier de destination.
        rate_limit: Nombre max de requêtes par seconde.
        progress: Afficher une barre de progression si stdout est un terminal.
        fmt: Format de sortie — 'pdf' (défaut) ou 'txt'.

    Returns:
        Rapport d'export avec statistiques.
    """
    from src.config import get_settings

    if output_dir is None:
        output_dir = get_settings().export_output_dir

    if not pages:
        return ExportReport(
            total_pages=0,
            exported=0,
            failed=0,
            total_size_bytes=0,
            results=[],
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[ExportResult] = []
    total_size = 0
    exported = 0
    failed = 0
    pages_count = len(pages)

    import click

    show_progress = progress and sys.stderr.isatty()

    click.echo(f"Exporting {pages_count} page(s)...")

    if show_progress:
        with Progress() as progress_bar:
            task = progress_bar.add_task("Export OneNote pages...", total=pages_count)
            for idx, (page_id, page_title) in enumerate(pages):
                click.echo(f"  [{idx + 1}/{pages_count}] {page_title}")
                result = await _export_page(
                    idx=idx,
                    page_id=page_id,
                    page_title=page_title,
                    client=client,
                    output_dir=output_dir,
                    rate_limit=rate_limit,
                    pages_count=pages_count,
                    fmt=fmt,
                )
                progress_bar.advance(task)
                results.append(result)
                if result.success:
                    exported += 1
                    total_size += result.size_bytes
                else:
                    failed += 1
                    click.echo(f"  [FAIL] {page_title}: {result.error}", err=True)
    else:
        for idx, (page_id, page_title) in enumerate(pages):
            click.echo(f"  [{idx + 1}/{pages_count}] {page_title}")
            result = await _export_page(
                idx=idx,
                page_id=page_id,
                page_title=page_title,
                client=client,
                output_dir=output_dir,
                rate_limit=rate_limit,
                pages_count=pages_count,
                fmt=fmt,
            )
            results.append(result)
            if result.success:
                exported += 1
                total_size += result.size_bytes
            else:
                failed += 1
                click.echo(f"  [FAIL] {page_title}: {result.error}", err=True)

    click.echo(f"Done: {exported} exported, {failed} failed, {total_size / 1024:.1f} KB total")

    if failed > 0:
        errors_log = output_dir / "errors.log"
        with errors_log.open("w") as f:
            for result in results:
                if not result.success:
                    f.write(f"{result.page_title}: {result.error}\n")

    return ExportReport(
        total_pages=pages_count,
        exported=exported,
        failed=failed,
        total_size_bytes=total_size,
        results=results,
    )
