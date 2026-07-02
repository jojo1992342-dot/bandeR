from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.core.utils import command_exists, run_command


def extract_audio_for_asr(video_path: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not command_exists(settings.ffmpeg_bin):
        raise RuntimeError("FFmpeg introuvable. Installez FFmpeg ou configurez FFMPEG_BIN.")

    args = [
        settings.ffmpeg_bin,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        str(output_path),
    ]
    result = run_command(args, timeout=None)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Extraction audio echouee")
    return output_path

