"""Parse SRT files, generate embeddings, and ingest into pgvector."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import psycopg
import srt
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

DB_URL = "postgresql://postgres:dev@localhost:5432/rag_videos"
SRT_DIR = Path(__file__).parent.parent / "data" / "srt"
MODEL_NAME = "all-MiniLM-L6-v2"
CHUNK_SECONDS = 60


def chunk_srt(srt_path: Path, chunk_seconds: int = CHUNK_SECONDS) -> list[dict]:
    """Group SRT subtitles into time-based chunks.

    Parameters
    ----------
    srt_path : Path
        Path to SRT file.
    chunk_seconds : int
        Duration of each chunk in seconds.

    Returns
    -------
    list[dict]
        List of chunks with text, start_time, end_time.
    """
    content = srt_path.read_text(encoding="utf-8", errors="replace")
    subs = list(srt.parse(content))

    if not subs:
        return []

    chunks = []
    current_texts: list[str] = []
    chunk_start = subs[0].start.total_seconds()
    chunk_end = chunk_start

    for sub in subs:
        start_sec = sub.start.total_seconds()
        end_sec = sub.end.total_seconds()

        if start_sec - chunk_start >= chunk_seconds and current_texts:
            chunks.append(
                {
                    "text": " ".join(current_texts),
                    "start_time": chunk_start,
                    "end_time": chunk_end,
                }
            )
            current_texts = []
            chunk_start = start_sec

        current_texts.append(sub.content.replace("\n", " ").strip())
        chunk_end = end_sec

    if current_texts:
        chunks.append(
            {
                "text": " ".join(current_texts),
                "start_time": chunk_start,
                "end_time": chunk_end,
            }
        )

    return chunks


def ingest_video(
    video_id: str,
    title: str,
    srt_path: Path,
    model: SentenceTransformer,
    conn: psycopg.Connection,
    *,
    youtube_url: str = "",
) -> int:
    """Ingest a single video's SRT into pgvector.

    Parameters
    ----------
    video_id : str
        Unique video identifier (YouTube ID).
    title : str
        Video title.
    srt_path : Path
        Path to the SRT file.
    model : SentenceTransformer
        Embedding model.
    conn : psycopg.Connection
        Database connection.
    youtube_url : str
        YouTube URL for reference.

    Returns
    -------
    int
        Number of chunks ingested.
    """
    chunks = chunk_srt(srt_path)
    if not chunks:
        logger.warning("No chunks for %s", video_id)
        return 0

    logger.info("Embedding %d chunks for '%s'", len(chunks), title)

    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False)

    with conn.cursor() as cur:
        # Upsert video record
        cur.execute(
            """
            INSERT INTO videos (id, title, youtube_url, chunks_count)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                youtube_url = EXCLUDED.youtube_url,
                chunks_count = EXCLUDED.chunks_count
            """,
            (video_id, title, youtube_url, len(chunks)),
        )

        # Insert embeddings
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            cur.execute(
                """
                INSERT INTO video_embeddings
                    (video_id, chunk_id, text, start_time, end_time, embedding)
                VALUES (%s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (video_id, chunk_id) DO UPDATE SET
                    text = EXCLUDED.text,
                    start_time = EXCLUDED.start_time,
                    end_time = EXCLUDED.end_time,
                    embedding = EXCLUDED.embedding
                """,
                (
                    video_id,
                    i,
                    chunk["text"],
                    chunk["start_time"],
                    chunk["end_time"],
                    f"[{','.join(str(float(x)) for x in emb)}]",
                ),
            )

    conn.commit()
    logger.info("Ingested %d chunks for '%s'", len(chunks), title)
    return len(chunks)


def ingest_all(srt_dir: Path = SRT_DIR) -> None:
    """Ingest all SRT files from a directory.

    Parameters
    ----------
    srt_dir : Path
        Directory containing SRT files named {video_id}.fr.srt
    """
    srt_files = sorted(srt_dir.glob("*.srt"))
    if not srt_files:
        logger.error("No SRT files found in %s", srt_dir)
        sys.exit(1)

    logger.info("Found %d SRT files", len(srt_files))
    logger.info("Loading model '%s'...", MODEL_NAME)
    model = SentenceTransformer(MODEL_NAME)

    conn = psycopg.connect(DB_URL)
    total_chunks = 0

    for srt_path in srt_files:
        video_id = srt_path.stem
        # Title from last segment of "--" separated filename
        parts = srt_path.stem.split("--")
        title = parts[-1].strip() if len(parts) > 1 else srt_path.stem
        count = ingest_video(video_id, title, srt_path, model, conn)
        total_chunks += count

    conn.close()
    logger.info("=== Done: %d chunks from %d files ===", total_chunks, len(srt_files))


def main() -> None:
    srt_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else SRT_DIR
    ingest_all(srt_dir)


if __name__ == "__main__":
    main()
