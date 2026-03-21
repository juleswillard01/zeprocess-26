"""Point d'entrée CLI pour OneNote Exporter."""

from __future__ import annotations

import asyncio
import logging

import click

from src.auth import AuthenticationError, authenticate, refresh_token
from src.exporter import export_batch, sanitize_filename
from src.graph import GraphClient
from src.hierarchy import HierarchyNode, build_tree, display_tree

logger = logging.getLogger(__name__)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Mode debug")
@click.option("--no-cache", is_flag=True, help="Ignorer le cache")
@click.option(
    "--notebook", "-n", default=None, help="Nom du notebook à cibler (override NOTEBOOK_NAME)"
)
@click.pass_context
def main(ctx: click.Context, verbose: bool, no_cache: bool, notebook: str | None) -> None:
    """OneNote Exporter — Extraire les pages OneNote en PDF."""
    import os

    from src.config import get_settings

    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["no_cache"] = no_cache
    ctx.obj["notebook"] = notebook

    if notebook:
        os.environ["NOTEBOOK_NAME"] = notebook
        get_settings.cache_clear()

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(message)s",
    )


@main.command()
@click.pass_context
def auth(ctx: click.Context) -> None:
    """Tester l'authentification Azure AD."""
    try:
        _token, _app = authenticate()
        click.echo("Authentification réussie")
    except AuthenticationError as e:
        click.echo(f"Erreur: {e}", err=True)
        ctx.exit(1)


@main.command()
@click.pass_context
def tree(ctx: click.Context) -> None:
    """Afficher la hiérarchie OneNote avec comptage de pages."""
    no_cache = ctx.obj.get("no_cache", False)
    try:
        token, _app = authenticate()
    except (AuthenticationError, ValueError) as e:
        click.echo(f"Erreur d'authentification: {e}", err=True)
        ctx.exit(1)
        return
    asyncio.run(_async_tree(token, no_cache))


async def _async_tree(token: str, no_cache: bool) -> None:
    """Coroutine pour la commande tree — un seul event loop."""
    client = GraphClient(access_token=token)
    try:
        nodes = await build_tree(client, no_cache=no_cache)
        output = display_tree(nodes)
        if output:
            click.echo(output)
    finally:
        await client.close()


@main.command()
@click.option("--sections", "-s", help="Sections à exporter (séparées par virgule)")
@click.option("--all", "export_all", is_flag=True, help="Exporter tout")
@click.option("--max-pages", type=int, default=150, help="Limite de pages [défaut: 150]")
@click.option("--output-dir", "-o", type=click.Path(), help="Dossier de sortie")
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["pdf", "txt"]),
    default="pdf",
    help="Format de sortie [défaut: pdf]",
)
@click.option(
    "--resume/--no-resume", default=True, help="Skip fichiers déjà exportés [défaut: resume]"
)
@click.pass_context
def export(
    ctx: click.Context,
    sections: str | None,
    export_all: bool,
    max_pages: int,
    output_dir: str | None,
    fmt: str,
    resume: bool,
) -> None:
    """Exporter les pages sélectionnées en PDF."""
    from pathlib import Path

    from src.config import get_settings

    settings = get_settings()
    out_path: Path = Path(output_dir) if output_dir else settings.export_output_dir

    try:
        token, app = authenticate()
    except (AuthenticationError, ValueError) as e:
        click.echo(f"Erreur d'authentification: {e}", err=True)
        ctx.exit(1)
        return

    # Sélection interactive AVANT asyncio.run (click.prompt est sync)
    no_cache = ctx.obj.get("no_cache", False)
    interactive_sections: list[HierarchyNode] | None = None
    if not sections and not export_all and _is_interactive():
        # Build tree juste pour la sélection interactive
        nodes_for_selection = asyncio.run(_quick_build_tree(token, no_cache))
        if nodes_for_selection:
            numbered = _build_numbered_sections(nodes_for_selection)
            for idx, path, sec in numbered:
                click.echo(f"  {idx}. {path} ({sec.page_count} pages)")
            selection = click.prompt("Sélection (ex: 1,3,5 ou 1-5)", default="")
            selected_indices = _parse_selection(selection, len(numbered))
            interactive_sections = [numbered[i - 1][2] for i in selected_indices]

    asyncio.run(
        _async_export(
            token=token,
            app=app,
            sections=sections,
            export_all=export_all,
            max_pages=max_pages,
            out_path=out_path,
            rate_limit=settings.graph_rate_limit,
            fmt=fmt,
            resume=resume,
            no_cache=no_cache,
            interactive_sections=interactive_sections,
        )
    )


@main.command()
@click.option("--dry-run", is_flag=True, help="Afficher le plan sans écrire")
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default="io/md",
    help="Dossier de sortie [défaut: io/md]",
)
@click.pass_context
def bundle(ctx: click.Context, dry_run: bool, output_dir: str) -> None:
    """Regrouper les exports TXT en 10 fichiers Markdown thématiques."""
    from pathlib import Path

    from src.bundler import bundle_all
    from src.config import get_settings

    settings = get_settings()
    export_dir = settings.export_output_dir
    out_path = Path(output_dir)

    click.echo(f"Bundling exports from {export_dir} → {out_path}")
    if dry_run:
        click.echo("[DRY RUN]")

    report = bundle_all(export_dir=export_dir, output_dir=out_path, dry_run=dry_run)

    total = sum(report.values())
    click.echo(f"\nTotal: {total} pages across {len(report)} files")


async def _quick_build_tree(token: str, no_cache: bool) -> list[HierarchyNode]:
    """Build tree dans un event loop dédié (pour la sélection interactive)."""
    client = GraphClient(access_token=token)
    try:
        return await build_tree(client, no_cache=no_cache)
    finally:
        await client.close()


async def _async_export(
    token: str,
    app: object,
    sections: str | None,
    export_all: bool,
    max_pages: int,
    out_path: object,
    rate_limit: int,
    fmt: str,
    resume: bool,
    no_cache: bool,
    interactive_sections: list[HierarchyNode] | None,
) -> None:
    """Coroutine pour l'export — un seul event loop pour tout le travail async."""
    from pathlib import Path as _Path

    import msal

    out = _Path(str(out_path))
    client = GraphClient(access_token=token)
    try:
        nodes = await build_tree(client, no_cache=no_cache)

        if interactive_sections is not None:
            sections_to_export = interactive_sections
        else:
            sections_to_export = _get_sections_to_export(nodes, sections, export_all)

        if not sections_to_export:
            click.echo("Aucune section sélectionnée.")
            return

        total_pages = sum(s.page_count for s in sections_to_export)
        if (
            export_all
            and total_pages > 200
            and not click.confirm(f"{total_pages} pages à exporter. Continuer ?")
        ):
            click.echo("Export annulé.")
            return

        total_exported = 0
        total_failed = 0
        for sec_idx, section_node in enumerate(sections_to_export):
            section_dir = out / sanitize_filename(section_node.name)
            pages_list = [
                (pid, section_node.page_titles.get(pid, pid)) for pid in section_node.page_ids
            ]
            if not pages_list:
                continue

            pages_list = pages_list[:max_pages]

            click.echo(
                f"\n[{sec_idx + 1}/{len(sections_to_export)}] "
                f"{section_node.name} ({len(pages_list)} pages)"
            )

            # Refresh token silencieusement
            if isinstance(app, msal.PublicClientApplication):
                try:
                    new_token = refresh_token(app)
                    client.update_token(new_token)
                except AuthenticationError:
                    pass

            report = await export_batch(
                pages=pages_list,
                client=client,
                output_dir=section_dir,
                rate_limit=rate_limit,
                fmt=fmt,
                resume=resume,
            )
            total_exported += report.exported
            total_failed += report.failed
            # Breathing room between sections to avoid rate limit cascading
            if sec_idx < len(sections_to_export) - 1:
                click.echo("  Cooldown 5s before next section...")
                await asyncio.sleep(5.0)

        click.echo(f"\nTotal: {total_exported} exported, {total_failed} failed")
    finally:
        await client.close()


def _is_interactive() -> bool:
    """Vérifie si stdin est un terminal interactif."""
    import sys

    return sys.stdin.isatty()


def _parse_selection(input_str: str, max_index: int) -> list[int]:
    """Parse une sélection interactive en liste d'indices.

    Supporte: "3", "1,3,5", "1-5", "1,3-5,8"

    Args:
        input_str: Chaîne de sélection de l'utilisateur.
        max_index: Index maximum valide.

    Returns:
        Liste triée et dédupliquée d'indices valides (1-based).
    """
    if not input_str.strip():
        return []

    indices: set[int] = set()
    parts = input_str.split(",")

    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                start_str, end_str = part.split("-", 1)
                start = int(start_str.strip())
                end = int(end_str.strip())
                for i in range(start, end + 1):
                    if 1 <= i <= max_index:
                        indices.add(i)
            except ValueError:
                continue
        else:
            try:
                idx = int(part)
                if 1 <= idx <= max_index:
                    indices.add(idx)
            except ValueError:
                continue

    return sorted(indices)


def _build_numbered_sections(
    nodes: list[HierarchyNode],
) -> list[tuple[int, str, HierarchyNode]]:
    """Flatten l'arbre pour numéroter toutes les sections.

    Args:
        nodes: Arbre de hiérarchie.

    Returns:
        Liste de (index_1_based, chemin_affichage, section_node).
    """
    sections: list[tuple[str, HierarchyNode]] = []
    for node in nodes:
        _collect_sections(node, node.name, sections)

    return [(i + 1, path, sec) for i, (path, sec) in enumerate(sections)]


def _collect_sections(
    node: HierarchyNode,
    path: str,
    sections: list[tuple[str, HierarchyNode]],
) -> None:
    """Parcourt récursivement pour collecter les sections."""
    if node.node_type == "section":
        sections.append((path, node))
    for child in node.children:
        child_path = f"{path}/{child.name}" if node.node_type != "section" else path
        _collect_sections(child, child_path, sections)


def _get_sections_to_export(
    nodes: list[HierarchyNode],
    sections: str | None,
    export_all: bool,
) -> list[HierarchyNode]:
    """Collecte les HierarchyNode sections à exporter.

    Args:
        nodes: Arbre de hiérarchie.
        sections: Noms séparés par virgule, ou None.
        export_all: Si True, toutes les sections.

    Returns:
        Liste de HierarchyNode de type section.
    """
    selected = [s.strip() for s in sections.split(",")] if sections else []
    result: list[HierarchyNode] = []

    def _collect(node: HierarchyNode) -> None:
        if node.node_type == "section" and (export_all or node.name in selected):
            result.append(node)
        for child in node.children:
            _collect(child)

    for node in nodes:
        _collect(node)
    return result


def _build_page_tuples(  # pyright: ignore[reportUnusedFunction]
    nodes: list[HierarchyNode],
    page_ids: list[str],
) -> list[tuple[str, str]]:
    """Construit les tuples (page_id, page_title) depuis l'arbre.

    Args:
        nodes: Arbre de hiérarchie.
        page_ids: IDs de pages à exporter.

    Returns:
        Liste de tuples (page_id, page_title).
    """
    titles: dict[str, str] = {}
    _collect_titles(nodes, titles)
    return [(pid, titles.get(pid, pid)) for pid in page_ids]


def _collect_titles(nodes: list[HierarchyNode], titles: dict[str, str]) -> None:
    """Collecte récursivement les titres de pages depuis l'arbre."""
    for node in nodes:
        if node.page_titles:
            titles.update(node.page_titles)
        _collect_titles(node.children, titles)


def _collect_page_ids(  # pyright: ignore[reportUnusedFunction]
    nodes: list[HierarchyNode],
    sections: str | None,
    export_all: bool,
    max_pages: int,
) -> list[str]:
    """Collecte les IDs de pages depuis l'arbre selon les filtres.

    Args:
        nodes: Arbre de hiérarchie.
        sections: Noms de sections séparés par virgule, ou None.
        export_all: Si True, exporter toutes les pages.
        max_pages: Limite maximale de pages.

    Returns:
        Liste d'IDs de pages à exporter.
    """
    selected_sections: list[str] = []
    if sections:
        selected_sections = [s.strip() for s in sections.split(",")]

    page_ids: list[str] = []
    for node in nodes:
        _collect_from_node(node, selected_sections, export_all, page_ids)

    return page_ids[:max_pages]


def _collect_from_node(
    node: HierarchyNode,
    selected_sections: list[str],
    export_all: bool,
    page_ids: list[str],
) -> None:
    """Parcourt récursivement l'arbre pour collecter les IDs de pages."""
    if node.node_type == "section" and (export_all or node.name in selected_sections):
        page_ids.extend(node.page_ids)
    for child in node.children:
        _collect_from_node(child, selected_sections, export_all, page_ids)


if __name__ == "__main__":
    main()
