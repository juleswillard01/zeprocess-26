"""Transcribe video/audio files to SRT using faster-whisper (local, CPU)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from faster_whisper import WhisperModel

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
SRT_DIR = Path(__file__).parent.parent / "data" / "srt"
MODEL_SIZE = "small"
MEDIA_EXTENSIONS = {".ts", ".mp4", ".m4a", ".mp3", ".mkv", ".avi", ".mov", ".webm"}


def format_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format HH:MM:SS,mmm."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def transcribe_file(
    file_path: Path,
    model: WhisperModel,
    output_dir: Path = SRT_DIR,
) -> Path | None:
    """Transcribe a single media file to SRT.

    Parameters
    ----------
    file_path : Path
        Path to audio/video file.
    model : WhisperModel
        Loaded faster-whisper model.
    output_dir : Path
        Directory for output SRT files.

    Returns
    -------
    Path | None
        Path to generated SRT, or None on failure.
    """
    # Use relative path from RAW_DIR as basis for SRT filename
    try:
        rel = file_path.relative_to(RAW_DIR)
    except ValueError:
        rel = Path(file_path.name)

    # Flatten path: Module1/video.TS -> Module1--video.srt
    srt_name = "--".join(rel.parts).rsplit(".", 1)[0] + ".srt"
    srt_path = output_dir / srt_name

    if srt_path.exists():
        logger.info("SKIP (exists): %s", srt_name)
        return srt_path

    logger.info("Transcribing: %s", file_path.name)

    try:
        segments, info = model.transcribe(
            str(file_path),
            language="fr",
            beam_size=5,
            vad_filter=True,
        )

        logger.info(
            "  Detected language: %s (prob %.2f), duration: %.0fs",
            info.language,
            info.language_probability,
            info.duration,
        )

        srt_lines: list[str] = []
        for i, seg in enumerate(segments, 1):
            srt_lines.append(str(i))
            srt_lines.append(
                f"{format_timestamp(seg.start)} --> {format_timestamp(seg.end)}"
            )
            srt_lines.append(seg.text.strip())
            srt_lines.append("")

        if not srt_lines:
            logger.warning("  No speech detected in %s", file_path.name)
            return None

        output_dir.mkdir(parents=True, exist_ok=True)
        srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
        logger.info("  Wrote: %s (%d segments)", srt_name, i)
        return srt_path

    except Exception:
        logger.error("  Failed to transcribe %s", file_path.name, exc_info=True)
        return None


def find_media_files(root: Path) -> list[Path]:
    """Find all media files recursively."""
    files = []
    for ext in MEDIA_EXTENSIONS:
        files.extend(root.rglob(f"*{ext}"))
        files.extend(root.rglob(f"*{ext.upper()}"))
    # Deduplicate (case-insensitive ext matching may overlap)
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in sorted(files):
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


def transcribe_all(raw_dir: Path = RAW_DIR) -> list[Path]:
    """Transcribe all media files in a directory.

    Parameters
    ----------
    raw_dir : Path
        Root directory containing media files.

    Returns
    -------
    list[Path]
        List of generated SRT file paths.
    """
    media_files = find_media_files(raw_dir)
    if not media_files:
        logger.error("No media files found in %s", raw_dir)
        return []

    logger.info("Found %d media files in %s", len(media_files), raw_dir)
    logger.info("Loading model '%s' (CPU)...", MODEL_SIZE)
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

    results: list[Path] = []
    for i, media_path in enumerate(media_files, 1):
        logger.info("[%d/%d] %s", i, len(media_files), media_path.name)
        srt_path = transcribe_file(media_path, model)
        if srt_path:
            results.append(srt_path)

    logger.info("=== Done: %d/%d files transcribed ===", len(results), len(media_files))
    return results


def main() -> None:
    raw_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else RAW_DIR
    transcribe_all(raw_dir)


if __name__ == "__main__":
    main()
