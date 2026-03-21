"""Tests pour le bundler de fichiers MD."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.bundler import (
    BundleGroup,
    PageEntry,
    _extract_title_from_filename,
    _make_anchor,
    build_markdown,
    bundle_all,
    clean_text,
    collect_pages,
    get_groups,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestCleanText:
    def test_strips_crlf(self) -> None:
        assert clean_text("hello\r\nworld\r\n") == "hello\nworld"

    def test_strips_leading_tabs(self) -> None:
        assert clean_text("\t\t\tindented") == "indented"

    def test_removes_graph_image_blobs(self) -> None:
        html = (
            'before src="https://graph.microsoft.com/v1.0/users'
            '/foo/onenote/resources/123/$value" data-src-type="image/png" after'
        )
        result = clean_text(html)
        assert "graph.microsoft.com" not in result
        assert "before" in result

    def test_collapses_blank_lines(self) -> None:
        assert clean_text("a\n\n\n\n\nb") == "a\n\nb"

    def test_strips_outer_whitespace(self) -> None:
        assert clean_text("  \n\n  hello  \n\n  ") == "hello"

    def test_empty_input(self) -> None:
        assert clean_text("") == ""

    def test_tabs_only(self) -> None:
        assert clean_text("\t\t\t") == ""


class TestExtractTitle:
    def test_numeric_prefix(self) -> None:
        assert _extract_title_from_filename("003_DHV.txt") == "DHV"

    def test_no_prefix(self) -> None:
        assert _extract_title_from_filename("some file.txt") == "some file"

    def test_empty_after_prefix(self) -> None:
        # "000_" has no match for \d{3}_(.+), so falls through to stem "000_"
        assert _extract_title_from_filename("000_.txt") == "000_"

    def test_complex_title(self) -> None:
        assert (
            _extract_title_from_filename("135_Escalade Sexuelle Calibrée By Jacques.txt")
            == "Escalade Sexuelle Calibrée By Jacques"
        )


class TestMakeAnchor:
    def test_simple(self) -> None:
        assert _make_anchor("Hello World") == "hello-world"

    def test_special_chars_stripped(self) -> None:
        result = _make_anchor("LR 5/7 by Jon")
        assert "/" not in result
        assert "lr" in result

    def test_empty(self) -> None:
        assert _make_anchor("") == ""


class TestCollectPages:
    def test_collects_from_single_dir(self, tmp_path: Path) -> None:
        section = tmp_path / "TestSection"
        section.mkdir()
        (section / "000_Page One.txt").write_text("Content of page one here which is long enough")
        (section / "001_Page Two.txt").write_text("Content of page two here which is long enough")

        pages = collect_pages(tmp_path, ["TestSection"])
        assert len(pages) == 2
        assert pages[0].title == "Page One"
        assert pages[1].title == "Page Two"

    def test_skips_empty_files(self, tmp_path: Path) -> None:
        section = tmp_path / "TestSection"
        section.mkdir()
        (section / "000_Empty.txt").write_text("")
        (section / "001_Real.txt").write_text("Some real content")

        pages = collect_pages(tmp_path, ["TestSection"])
        assert len(pages) == 1
        assert pages[0].title == "Real"

    def test_missing_dir_skipped(self, tmp_path: Path) -> None:
        pages = collect_pages(tmp_path, ["NonExistent"])
        assert len(pages) == 0

    def test_stub_detection(self, tmp_path: Path) -> None:
        section = tmp_path / "S1"
        section.mkdir()
        (section / "000_Short.txt").write_text("tiny")
        (section / "001_Long.txt").write_text("x" * 600)

        pages = collect_pages(tmp_path, ["S1"])
        assert pages[0].is_stub is True
        assert pages[1].is_stub is False

    def test_skips_gitkeep(self, tmp_path: Path) -> None:
        section = tmp_path / "S1"
        section.mkdir()
        (section / ".gitkeep").write_text("")
        (section / "000_Real.txt").write_text("content")

        pages = collect_pages(tmp_path, ["S1"])
        assert len(pages) == 1

    def test_multiple_sections_sorted(self, tmp_path: Path) -> None:
        s1 = tmp_path / "Alpha"
        s2 = tmp_path / "Beta"
        s1.mkdir()
        s2.mkdir()
        (s1 / "000_A1.txt").write_text("a1 content")
        (s2 / "000_B1.txt").write_text("b1 content")

        pages = collect_pages(tmp_path, ["Alpha", "Beta"])
        assert len(pages) == 2
        assert pages[0].source_section == "Alpha"
        assert pages[1].source_section == "Beta"


class TestBuildMarkdown:
    def test_empty_pages(self) -> None:
        group = BundleGroup("Test", "test.md", ["S1"])
        md = build_markdown(group, [])
        assert "Aucune page" in md

    def test_has_header_and_toc(self, tmp_path: Path) -> None:
        group = BundleGroup("My Group", "test.md", ["S1"])
        pages = [
            PageEntry(
                0, "Page One", "Content one", "S1", tmp_path / "000_Page One.txt", is_stub=False
            ),
            PageEntry(
                1, "Page Two", "Content two", "S1", tmp_path / "001_Page Two.txt", is_stub=False
            ),
        ]
        md = build_markdown(group, pages)
        assert "# My Group — 2 pages" in md
        assert "## Table des matières" in md
        assert "[Page One]" in md
        assert "[Page Two]" in md
        assert "Content one" in md
        assert "Content two" in md

    def test_stub_marked(self, tmp_path: Path) -> None:
        group = BundleGroup("Test", "test.md", ["S1"])
        pages = [
            PageEntry(0, "Stub Page", "tiny", "S1", tmp_path / "000_Stub.txt", is_stub=True),
        ]
        md = build_markdown(group, pages)
        assert "*(stub)*" in md
        assert "Contenu trop court" in md


class TestBundleAll:
    def test_dry_run_no_files_created(self, tmp_path: Path) -> None:
        export_dir = tmp_path / "exports"
        export_dir.mkdir()
        output_dir = tmp_path / "md"

        report = bundle_all(export_dir, output_dir, dry_run=True)
        assert not output_dir.exists()
        assert isinstance(report, dict)

    def test_creates_output_files(self, tmp_path: Path) -> None:
        export_dir = tmp_path / "exports"
        output_dir = tmp_path / "md"
        # Create one section that matches a group
        jon_dir = export_dir / "JON"
        jon_dir.mkdir(parents=True)
        (jon_dir / "000_Test Page.txt").write_text("Test content for JON section")

        report = bundle_all(export_dir, output_dir, dry_run=False)
        assert output_dir.exists()
        # JON group should have 1 page
        assert report["08_JON.md"] == 1
        assert (output_dir / "08_JON.md").exists()


class TestGetGroups:
    def test_returns_10_groups(self) -> None:
        groups = get_groups()
        assert len(groups) == 10

    def test_all_have_output_filenames(self) -> None:
        groups = get_groups()
        for g in groups:
            assert g.output_filename.endswith(".md")
            assert g.name

    def test_no_duplicate_output_filenames(self) -> None:
        groups = get_groups()
        filenames = [g.output_filename for g in groups]
        assert len(filenames) == len(set(filenames))
