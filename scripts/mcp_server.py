"""MCP server for semantic search over video training content."""

from __future__ import annotations

import logging

import psycopg
from mcp.server.fastmcp import FastMCP
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

DB_URL = "postgresql://postgres:dev@localhost:5432/rag_videos"
MODEL_NAME = "all-MiniLM-L6-v2"

mcp = FastMCP("video-rag")

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Lazy-load embedding model."""
    global _model
    if _model is None:
        logger.info("Loading model '%s'...", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
    return _model


@mcp.tool()
def search_videos(query: str, top_k: int = 5) -> str:
    """Search training video content by semantic similarity.

    Parameters
    ----------
    query : str
        Natural language search query in French or English.
    top_k : int
        Number of results to return (default 5).

    Returns
    -------
    str
        Formatted search results with video title, timestamp, text, and score.
    """
    model = get_model()
    embedding = model.encode([query])[0]
    emb_str = f"[{','.join(str(float(x)) for x in embedding)}]"

    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                e.text,
                e.start_time,
                e.end_time,
                v.title,
                v.youtube_url,
                1 - (e.embedding <=> %s::vector) AS similarity
            FROM video_embeddings e
            JOIN videos v ON v.id = e.video_id
            ORDER BY e.embedding <=> %s::vector
            LIMIT %s
            """,
            (emb_str, emb_str, top_k),
        )
        rows = cur.fetchall()

    if not rows:
        return "No results found."

    lines: list[str] = []
    for i, (text, start, end, title, url, score) in enumerate(rows, 1):
        mins = int(start // 60)
        secs = int(start % 60)
        lines.append(f"--- Result {i} (score: {score:.4f}) ---")
        lines.append(f"Video: {title}")
        lines.append(f"Timestamp: {mins}:{secs:02d}")
        lines.append(f"Text: {text[:300]}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def list_videos() -> str:
    """List all indexed training videos with their chunk counts.

    Returns
    -------
    str
        Formatted list of all videos in the database.
    """
    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT id, title, chunks_count FROM videos ORDER BY title")
        rows = cur.fetchall()

    if not rows:
        return "No videos indexed yet."

    lines: list[str] = [f"Total: {len(rows)} videos\n"]
    for vid, title, chunks in rows:
        lines.append(f"- {title} ({chunks} chunks)")

    return "\n".join(lines)


@mcp.tool()
def get_video_context(video_title: str) -> str:
    """Get full transcript of a specific video by title (partial match).

    Parameters
    ----------
    video_title : str
        Partial or full video title to search for.

    Returns
    -------
    str
        Full transcript text ordered by timestamp.
    """
    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT v.title, e.text, e.start_time, e.end_time
            FROM video_embeddings e
            JOIN videos v ON v.id = e.video_id
            WHERE v.title ILIKE %s
            ORDER BY v.title, e.start_time
            """,
            (f"%{video_title}%",),
        )
        rows = cur.fetchall()

    if not rows:
        return f"No video found matching '{video_title}'."

    lines: list[str] = []
    current_title = ""
    for title, text, start, end in rows:
        if title != current_title:
            current_title = title
            lines.append(f"\n=== {title} ===\n")
        mins = int(start // 60)
        secs = int(start % 60)
        lines.append(f"[{mins}:{secs:02d}] {text}")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
