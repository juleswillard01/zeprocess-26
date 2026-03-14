"""Full RAG pipeline orchestrator: transcribe → embed → ingest."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
SRT_DIR = Path(__file__).parent.parent / "data" / "srt"


def run_pipeline(raw_dir: Path = RAW_DIR) -> None:
    """Run full pipeline: transcribe media files then ingest embeddings.

    Parameters
    ----------
    raw_dir : Path
        Directory containing raw media files.
    """
    # Step 1: Transcribe
    logger.info("=== STEP 1: Transcribe media → SRT ===")
    from transcribe import transcribe_all

    srt_files = transcribe_all(raw_dir)
    if not srt_files:
        logger.error("No SRT files generated, aborting.")
        sys.exit(1)
    logger.info("Generated %d SRT files", len(srt_files))

    # Step 2: Embed + Ingest
    logger.info("=== STEP 2: Embed SRT → pgvector ===")
    from embed_ingest import ingest_all

    ingest_all(SRT_DIR)

    # Step 3: Verify
    logger.info("=== STEP 3: Verify ===")
    from search_videos import search

    results = search("comment séduire")
    if results:
        logger.info("Search test OK — %d results for 'comment séduire'", len(results))
        logger.info(
            "Top result: '%s' (score: %.4f)", results[0]["title"], results[0]["score"]
        )
    else:
        logger.warning("Search returned no results — pipeline may have issues")

    logger.info("=== Pipeline complete ===")


def main() -> None:
    raw_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else RAW_DIR
    run_pipeline(raw_dir)


if __name__ == "__main__":
    main()
