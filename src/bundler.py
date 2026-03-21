"""Regroupement des exports TXT en fichiers Markdown thématiques."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import click

logger = logging.getLogger(__name__)

_STUB_THRESHOLD = 500
_GRAPH_IMAGE_PATTERN = re.compile(r'src="https://graph\.microsoft\.com/[^"]*"[^>]*', re.IGNORECASE)


@dataclass
class BundleGroup:
    """Définition d'un groupe thématique."""

    name: str
    output_filename: str
    section_dirs: list[str] = field(default_factory=lambda: [])


@dataclass
class PageEntry:
    """Une page extraite d'un fichier TXT."""

    order: int
    title: str
    content: str
    source_section: str
    source_file: Path
    is_stub: bool = False


def get_groups() -> list[BundleGroup]:
    """Returns the 10 thematic group definitions."""
    return [
        BundleGroup("REVELATION LR", "01_REVELATION_LR.md", ["Revelation LR"]),
        BundleGroup(
            "REVELATION VALUE",
            "02_REVELATION_VALUE.md",
            ["Revelation TXT VALUE", "Revelation Value"],
        ),
        BundleGroup("LES COACHS", "03_LES_COACHS.md", ["Les Coachs se Lachent"]),
        BundleGroup("VALUE", "04_VALUE.md", ["VALUE", "Value", "Lindberg Model"]),
        BundleGroup("LR", "05_LR.md", ["LR"]),
        BundleGroup(
            "REVELATION FR",
            "06_REVELATION_FR.md",
            [
                "Revelation FR",
                "Revelation Questions",
                "Revelation TINDER Profil",
                "REVELATION 2",
            ],
        ),
        BundleGroup(
            "TXTGAME",
            "07_TXTGAME.md",
            [
                "Revelation TXTGAME",
                "TXT",
                "TXTGAME BLUEPRInt",
            ],
        ),
        BundleGroup("JON", "08_JON.md", ["JON", "Jon Notes", "Jon HTML"]),
        BundleGroup(
            "FR & CHALLENGE",
            "09_FR_CHALLENGE.md",
            [
                "FR",
                "CHALLENGE",
                "Avant-Propos",
                "BOOTCAMP",
                "0822 EAST EURO",
                "2025",
                "2k23",
            ],
        ),
        BundleGroup(
            "MISC",
            "10_MISC.md",
            [
                "SEXU",
                "LOUP_DDP",
                "ARTICLES FONDATEURS",
                "AUTRES",
                "OTHER",
                "CONV",
                "Soumission",
                "C1 - Cameras Cachées",
                "M1 - La Carte",
                "M2 - Avancer dans la Carte",
                "OLD PDF",
                "Vierge",
                "RESUME",
                "LIVE",
                "NATURAL",
                "Naabz",
                "LIVRES",
                "TA",
                "Tder",
                "Intro",
                "New Section 1",
                "QdA",
            ],
        ),
    ]


def clean_text(raw: str) -> str:
    """Normalise un texte TXT exporté : strip tabs, CRLF→LF, remove image blobs.

    Args:
        raw: Raw text content from exported TXT file.

    Returns:
        Cleaned text.
    """
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    # Strip leading tabs from each line (OneNote export indentation)
    lines = text.split("\n")
    lines = [line.lstrip("\t") for line in lines]
    text = "\n".join(lines)
    # Remove Graph API image URL blobs
    text = _GRAPH_IMAGE_PATTERN.sub("", text)
    # Remove leftover img tag fragments
    text = re.sub(r"<img\s*/?\s*>", "", text, flags=re.IGNORECASE)
    # Collapse excessive blank lines (3+ → 2)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_title_from_filename(filename: str) -> str:
    """Extract the human title from a filename like '003_DHV.txt'.

    Args:
        filename: Filename with optional numeric prefix.

    Returns:
        Human-readable title.
    """
    name = Path(filename).stem  # Remove .txt
    # Remove numeric prefix like "003_"
    match = re.match(r"^\d{3}_(.+)$", name)
    if match:
        return match.group(1).strip()
    return name.strip()


def _escape_md(title: str) -> str:
    """Escape brackets to prevent Markdown link injection."""
    return title.replace("[", "\\[").replace("]", "\\]")


def _make_anchor(title: str) -> str:
    """Generate a markdown-compatible anchor from a title.

    Args:
        title: Page title.

    Returns:
        Lowercase anchor slug.
    """
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"\s+", "-", slug).strip("-")
    return slug


def collect_pages(export_dir: Path, section_dirs: list[str]) -> list[PageEntry]:
    """Collect and parse all TXT files from the given section directories.

    Args:
        export_dir: Root export directory (io/exports).
        section_dirs: List of section directory names to include.

    Returns:
        Sorted list of PageEntry objects.
    """
    pages: list[PageEntry] = []

    for section_name in section_dirs:
        section_path = export_dir / section_name
        if not section_path.is_dir():
            logger.warning("Section directory not found: %s", section_path)
            continue

        for txt_file in sorted(section_path.glob("*.txt")):
            if txt_file.name == ".gitkeep":
                continue

            try:
                raw_content = txt_file.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                logger.error("Cannot read %s: %s", txt_file, exc)
                continue

            # Skip empty files
            if not raw_content.strip():
                continue

            title = _extract_title_from_filename(txt_file.name)
            if not title:
                title = f"[Sans titre — {txt_file.name}]"

            content = clean_text(raw_content)
            is_stub = len(content.encode("utf-8")) < _STUB_THRESHOLD

            # Extract order from filename prefix
            order_match = re.match(r"^(\d{3})_", txt_file.name)
            order = int(order_match.group(1)) if order_match else 999

            pages.append(
                PageEntry(
                    order=order,
                    title=title,
                    content=content,
                    source_section=section_name,
                    source_file=txt_file,
                    is_stub=is_stub,
                )
            )

    # Sort by section then order
    pages.sort(key=lambda p: (p.source_section, p.order))
    return pages


def build_markdown(group: BundleGroup, pages: list[PageEntry]) -> str:
    """Build a complete Markdown document with table of contents.

    Args:
        group: The bundle group definition.
        pages: List of pages to include.

    Returns:
        Complete Markdown string.
    """
    if not pages:
        return f"# {group.name}\n\n*Aucune page trouvée.*\n"

    lines: list[str] = []

    # Header
    page_count = len(pages)
    lines.append(f"# {group.name} — {page_count} pages\n")

    # Table of contents
    lines.append("## Table des matières\n")
    current_section = ""
    for entry_num, page in enumerate(pages, 1):
        if page.source_section != current_section:
            current_section = page.source_section
            lines.append(f"\n### {current_section}\n")
        anchor = _make_anchor(page.title)
        stub_marker = " *(stub)*" if page.is_stub else ""
        safe_title = _escape_md(page.title)
        lines.append(f"{entry_num}. [{safe_title}](#{anchor}){stub_marker}")

    lines.append("\n---\n")

    # Content
    current_section = ""
    for _idx, page in enumerate(pages, 1):
        if page.source_section != current_section:
            current_section = page.source_section
            lines.append(f"\n---\n\n# Section : {current_section}\n")

        lines.append(f"\n## {_escape_md(page.title)}\n")
        lines.append(f"> Source : {page.source_section} | Fichier : {page.source_file.name}\n")

        if page.is_stub:
            lines.append("*[Contenu trop court ou vide]*\n")

        lines.append(page.content)
        lines.append("\n\n---\n")

    return "\n".join(lines)


def bundle_all(
    export_dir: Path,
    output_dir: Path,
    dry_run: bool = False,
) -> dict[str, int]:
    """Generate all 10 MD files from the export directory.

    Args:
        export_dir: Root export directory containing section subdirs.
        output_dir: Directory where MD files will be written.
        dry_run: If True, only report what would be done.

    Returns:
        Dict mapping output filename to page count.
    """
    groups = get_groups()
    report: dict[str, int] = {}

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    for group in groups:
        pages = collect_pages(export_dir, group.section_dirs)
        report[group.output_filename] = len(pages)

        if dry_run:
            click.echo(
                f"  [DRY] {group.output_filename}: {len(pages)} pages from {group.section_dirs}"
            )
            continue

        md_content = build_markdown(group, pages)
        out_path = output_dir / group.output_filename
        out_path.write_text(md_content, encoding="utf-8")
        size_kb = out_path.stat().st_size / 1024
        click.echo(f"  {group.output_filename}: {len(pages)} pages, {size_kb:.0f} KB")

    return report
