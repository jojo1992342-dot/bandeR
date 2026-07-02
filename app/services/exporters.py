from __future__ import annotations

import html
import json
from pathlib import Path

from app.config import settings
from app.core.utils import command_exists, json_dumps, run_command

PLAY_RES_X = 1920
PLAY_RES_Y = 1080
RYTHMO_Y = 870
PLAYHEAD_X = 690
PIXELS_PER_SECOND = 230
PRE_ROLL = 3.0
POST_ROLL = 3.0


def export_json(project: dict, transcript: dict, rythmo: dict, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {"project": project, "transcript": transcript, "rythmo": rythmo},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return output


def export_xml(project: dict, transcript: dict, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [f'<project id="{html.escape(project["id"])}" name="{html.escape(project["name"])}">']
    for segment in transcript.get("segments", []):
        lines.append(
            f'  <segment id="{segment["id"]}" start="{segment["start_time"]:.3f}" end="{segment["end_time"]:.3f}">'
        )
        lines.append(f"    <text>{html.escape(segment['text'])}</text>")
        for word in segment.get("words", []):
            lines.append(
                f'    <word id="{word["id"]}" start="{word["start_time"]:.3f}" end="{word["end_time"]:.3f}">'
                f"{html.escape(word['text'])}</word>"
            )
        lines.append("  </segment>")
    lines.append("</project>")
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def export_srt(transcript: dict, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    blocks = []
    for idx, segment in enumerate(transcript.get("segments", []), start=1):
        blocks.append(
            "\n".join(
                [
                    str(idx),
                    f"{_srt_time(segment['start_time'])} --> {_srt_time(segment['end_time'])}",
                    segment["text"],
                ]
            )
        )
    output.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return output


def export_vtt(transcript: dict, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    blocks = ["WEBVTT", ""]
    for segment in transcript.get("segments", []):
        blocks.append(f"{_vtt_time(segment['start_time'])} --> {_vtt_time(segment['end_time'])}")
        blocks.append(segment["text"])
        blocks.append("")
    output.write_text("\n".join(blocks), encoding="utf-8")
    return output


def export_ass(transcript: dict, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_build_rythmo_ass(transcript), encoding="utf-8")
    return output


def export_video_with_rythmo(source_video: Path, transcript: dict, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    if not command_exists(settings.ffmpeg_bin):
        raise RuntimeError(f"FFmpeg introuvable: {settings.ffmpeg_bin}")
    ass_path = output.with_suffix(".ass")
    ass_path.write_text(_build_rythmo_ass(transcript), encoding="utf-8")
    filter_path = _ffmpeg_filter_path(ass_path)
    subtitle_filter = f"ass='{filter_path}'"

    attempts = [
        [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            str(source_video),
            "-vf",
            subtitle_filter,
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-threads",
            "1",
            "-x264-params",
            "bframes=0:ref=1:sync-lookahead=0:rc-lookahead=0",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(output),
        ],
        [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            str(source_video),
            "-vf",
            f"scale='min(1280,iw)':-2,{subtitle_filter}",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "25",
            "-pix_fmt",
            "yuv420p",
            "-threads",
            "1",
            "-x264-params",
            "bframes=0:ref=1:sync-lookahead=0:rc-lookahead=0",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            str(output),
        ],
    ]

    errors = []
    for args in attempts:
        if output.exists():
            output.unlink()
        result = run_command(args, timeout=None)
        if result.returncode == 0 and output.exists() and output.stat().st_size > 0:
            return output
        errors.append(_tail(result.stderr or result.stdout or "Export video echoue"))
    raise RuntimeError("Export video echoue apres deux tentatives.\n" + "\n---\n".join(errors))


def export_report(settings: dict, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json_dumps(settings), encoding="utf-8")
    return output


def _build_rythmo_ass(transcript: dict) -> str:
    events = []
    duration = _transcript_duration(transcript)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {PLAY_RES_X}
PlayResY: {PLAY_RES_Y}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Rythmo,Arial,46,&H00FFFFFF,&H0040D9A4,&H00111111,&HA0000000,1,0,1,3,0,5,0,0,0,1
Style: Guide,Arial,64,&H0040D9A4,&H0040D9A4,&H00111111,&H00000000,1,0,1,2,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""
    if duration > 0:
        events.append(
            f"Dialogue: 0,{_ass_time(0)},{_ass_time(duration + POST_ROLL)},Guide,,0,0,0,,"
            f"{{\\pos({PLAYHEAD_X},{RYTHMO_Y})\\alpha&H20&}}|"
        )
    for segment in transcript.get("segments", []):
        words = segment.get("words") or []
        for lane_index, word in enumerate(words):
            start = float(word.get("start_time", segment.get("start_time", 0)))
            end = float(word.get("end_time", max(start + 0.2, segment.get("end_time", start + 0.2))))
            if end <= start:
                end = start + 0.12
            event_start = max(0.0, start - PRE_ROLL)
            event_end = end + POST_ROLL
            x0 = int(PLAYHEAD_X + (start - event_start) * PIXELS_PER_SECOND)
            x1 = int(PLAYHEAD_X - (event_end - start) * PIXELS_PER_SECOND)
            y = RYTHMO_Y + ((lane_index % 2) * 58)
            text = _ass_escape(str(word.get("text", "")))
            if not text:
                continue
            body = f"{{\\move({x0},{y},{x1},{y})\\fad(80,80)}}{text}"
            events.append(f"Dialogue: 1,{_ass_time(event_start)},{_ass_time(event_end)},Rythmo,,0,0,0,,{body}")
    return header + "\n" + "\n".join(events) + "\n"


def _transcript_duration(transcript: dict) -> float:
    values = [float(segment.get("end_time", 0) or 0) for segment in transcript.get("segments", [])]
    return max(values) if values else 0.0


def _ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "").replace("}", "").replace("\n", r"\N").strip()


def _srt_time(seconds: float) -> str:
    h, rem = divmod(float(seconds), 3600)
    m, s = divmod(rem, 60)
    ms = int(round((s - int(s)) * 1000))
    return f"{int(h):02}:{int(m):02}:{int(s):02},{ms:03}"


def _vtt_time(seconds: float) -> str:
    return _srt_time(seconds).replace(",", ".")


def _ass_time(seconds: float) -> str:
    h, rem = divmod(max(0.0, float(seconds)), 3600)
    m, s = divmod(rem, 60)
    cs = int(round((s - int(s)) * 100))
    return f"{int(h)}:{int(m):02}:{int(s):02}.{cs:02}"


def _ffmpeg_filter_path(path: Path) -> str:
    value = path.resolve().as_posix()
    return value.replace(":", r"\:").replace("'", r"\'")


def _tail(text: str, lines: int = 18) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])
