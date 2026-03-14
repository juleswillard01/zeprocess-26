"""Search video embeddings in pgvector — CLI tool and reusable module."""

from __future__ import annotations

import logging
import sys

import psycopg
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

DB_URL = "postgresql://postgres:dev@localhost:5432/rag_videos"
MODEL_NAME = "all-MiniLM-L6-v2"


def search(
    query: str,
    *,
    top_k: int = 5,
    model: SentenceTransformer | None = None,
    conn: psycopg.Connection | None = None,
) -> list[dict]:
    """Search video chunks by semantic similarity.

    Parameters
    ----------
    query : str
        Natural language search query.
    top_k : int
        Number of results to return.
    model : SentenceTransformer | None
        Pre-loaded model (avoids reload).
    conn : psycopg.Connection | None
        Pre-existing DB connection.

    Returns
    -------
    list[dict]
        Matching chunks with video info, text, timestamps, and score.
    """
    if model is None:
        model = SentenceTransformer(MODEL_NAME)

    embedding = model.encode([query])[0]
    emb_str = f"[{','.join(str(float(x)) for x in embedding)}]"

    own_conn = conn is None
    if own_conn:
        conn = psycopg.connect(DB_URL)

    with conn.cursor() as cur:
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

    if own_conn:
        conn.close()

    results = []
    for text, start, end, title, url, score in rows:
        minutes_start = int(start // 60)
        seconds_start = int(start % 60)
        results.append(
            {
                "title": title,
                "text": text,
                "start": f"{minutes_start}:{seconds_start:02d}",
                "end_time": end,
                "youtube_url": url,
                "score": round(float(score), 4),
            }
        )

    return results


def main() -> None:
    if len(sys.argv) < 2:
        logger.error("Usage: python search_videos.py <query>")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    logger.info("Searching: '%s'", query)

    results = search(query)
    if not results:
        logger.info("No results found.")
        return

    for i, r in enumerate(results, 1):
        print(f"\n--- Result {i} (score: {r['score']}) ---")
        print(f"Video: {r['title']}")
        print(f"Time: {r['start']}")
        if r["youtube_url"]:
            print(f"URL: {r['youtube_url']}")
        print(f"Text: {r['text'][:200]}...")


if __name__ == "__main__":
    main()
