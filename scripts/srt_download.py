"""Download auto-generated SRT subtitles from YouTube videos using yt-dlp."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "srt"


def download_srt(youtube_url: str, output_dir: Path = OUTPUT_DIR) -> Path | None:
    """Download auto-generated French SRT from a YouTube video.

    Parameters
    ----------
    youtube_url : str
        Full YouTube URL (unlisted or public).
    output_dir : Path
        Directory to save SRT files.

    Returns
    -------
    Path | None
        Path to downloaded SRT file, or None on failure.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-auto-sub",
        "--sub-lang",
        "fr",
        "--sub-format",
        "srt",
        "--convert-subs",
        "srt",
        "-o",
        str(output_dir / "%(id)s.%(ext)s"),
        youtube_url,
    ]

    logger.info("Downloading SRT: %s", youtube_url)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        logger.error("yt-dlp failed: %s", result.stderr.strip())
        return None

    # Find the downloaded SRT
    srt_files = list(output_dir.glob("*.srt"))
    if not srt_files:
        logger.error("No SRT file found after download")
        return None

    latest = max(srt_files, key=lambda f: f.stat().st_mtime)
    logger.info("Downloaded: %s", latest.name)
    return latest


def download_batch(urls_file: Path) -> list[Path]:
    """Download SRTs for all URLs in a text file (one per line).

    Parameters
    ----------
    urls_file : Path
        Text file with one YouTube URL per line.

    Returns
    -------
    list[Path]
        List of successfully downloaded SRT paths.
    """
    urls = [
        line.strip()
        for line in urls_file.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    logger.info("Processing %d URLs", len(urls))

    downloaded = []
    for url in urls:
        srt_path = download_srt(url)
        if srt_path:
            downloaded.append(srt_path)

    logger.info("Downloaded %d/%d SRTs", len(downloaded), len(urls))
    return downloaded


def main() -> None:
    if len(sys.argv) < 2:
        logger.error("Usage: python srt_download.py <youtube_url_or_file>")
        sys.exit(1)

    target = sys.argv[1]

    if Path(target).is_file():
        download_batch(Path(target))
    else:
        download_srt(target)


if __name__ == "__main__":
    main()
