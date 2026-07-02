from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.utils import command_exists, run_command


def probe_media(path: Path) -> dict[str, Any]:
    if not command_exists(settings.ffprobe_bin):
        return {"duration": None, "fps": None, "width": None, "height": None, "codec": None}

    args = [
        settings.ffprobe_bin,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    result = run_command(args, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")

    data = json.loads(result.stdout)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    fmt = data.get("format", {})
    duration = float(fmt["duration"]) if fmt.get("duration") else None
    fps = _parse_fps(video.get("avg_frame_rate") or video.get("r_frame_rate"))
    return {
        "duration": duration,
        "fps": fps,
        "width": video.get("width"),
        "height": video.get("height"),
        "codec": video.get("codec_name"),
    }


def _parse_fps(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        num, den = value.split("/", 1)
        den_f = float(den)
        return float(num) / den_f if den_f else None
    return float(value)

