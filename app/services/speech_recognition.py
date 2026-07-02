from __future__ import annotations

import json
from pathlib import Path

from app.config import settings
from app.core.utils import command_exists, run_command


def transcribe_audio(audio_path: Path | None, duration: float | None, language: str = "fr") -> list[dict]:
    if (
        audio_path
        and audio_path.exists()
        and audio_path.suffix.lower() in {".wav", ".mp3", ".flac", ".m4a", ".ogg"}
        and settings.whisper_cpp_bin
        and settings.whisper_model
        and command_exists(settings.whisper_cpp_bin)
    ):
        segments = _transcribe_with_whisper_cpp(audio_path, language)
        if segments:
            return segments
    return _fallback_transcript(duration)


def _transcribe_with_whisper_cpp(audio_path: Path, language: str) -> list[dict]:
    output_prefix = audio_path.with_suffix("")
    args = [
        settings.whisper_cpp_bin or "whisper-cli",
        "-m",
        settings.whisper_model or "",
        "-f",
        str(audio_path),
        "-l",
        language,
        "-oj",
        "-ojf",
        "-of",
        str(output_prefix),
    ]
    result = run_command(args, timeout=None)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "whisper.cpp a echoue")

    json_path = output_prefix.with_suffix(".json")
    if not json_path.exists():
        return []

    data = json.loads(json_path.read_text(encoding="utf-8"))
    segments = []
    for item in data.get("transcription", data.get("segments", [])):
        if "offsets" in item:
            start = _milliseconds_to_seconds(item.get("offsets", {}).get("from"))
            end = _milliseconds_to_seconds(item.get("offsets", {}).get("to"))
        else:
            start = _timestamp_to_seconds(item.get("start"))
            end = _timestamp_to_seconds(item.get("end"))
        text = _repair_text(item.get("text", "").strip())
        words = _words_from_tokens(item.get("tokens", []), start, end)
        if text:
            segments.append(
                {
                    "start_time": float(start or 0),
                    "end_time": float(end or start or 0),
                    "text": text,
                    "words": words,
                    "confidence": _average_confidence(item.get("tokens", []), 0.85),
                    "source": "asr",
                }
            )
    return segments


def _words_from_tokens(tokens: list[dict], segment_start: float, segment_end: float) -> list[dict]:
    words: list[dict] = []
    current: dict | None = None
    for token in tokens:
        raw = token.get("text", "")
        if raw.startswith("[") and raw.endswith("]"):
            continue
        text = _repair_text(raw)
        if not text.strip():
            continue
        start = _milliseconds_to_seconds(token.get("offsets", {}).get("from"))
        end = _milliseconds_to_seconds(token.get("offsets", {}).get("to"))
        prob = float(token.get("p", 0.85))
        starts_new_word = raw.startswith(" ") or current is None
        piece = text.strip() if starts_new_word else text
        if starts_new_word:
            if current:
                words.append(current)
            current = {
                "text": piece,
                "normalized_text": piece.lower(),
                "start_time": start or segment_start,
                "end_time": max(end, start + 0.04),
                "confidence": prob,
            }
        else:
            current["text"] += piece
            current["normalized_text"] = current["text"].lower()
            current["end_time"] = max(float(current["end_time"]), end, float(current["start_time"]) + 0.04)
            current["confidence"] = min(float(current.get("confidence", prob)), prob)
    if current:
        words.append(current)
    return _clamp_words(words, segment_start, segment_end)


def _clamp_words(words: list[dict], start: float, end: float) -> list[dict]:
    cleaned = []
    previous_end = start
    for word in words:
        item = dict(word)
        item["start_time"] = max(start, float(item["start_time"]), previous_end)
        item["end_time"] = min(max(float(item["end_time"]), item["start_time"] + 0.04), end)
        previous_end = item["end_time"]
        if item["text"].strip():
            cleaned.append(item)
    return cleaned


def _fallback_transcript(duration: float | None) -> list[dict]:
    total = duration or 18.0
    samples = [
        "Bonjour, cette replique a ete generee localement pour initialiser la bande rythmo.",
        "Whisper n'a pas produit de transcription exploitable. Verifiez FFmpeg, le modele et le fichier audio extrait.",
        "Chaque mot peut etre corrige, deplace et exporte depuis l'application.",
    ]
    cursor = 1.0
    segments = []
    for idx, text in enumerate(samples):
        span = min(4.0 + idx, max(2.5, total / 5))
        if cursor >= total:
            break
        end = min(cursor + span, total)
        segments.append(
            {
                "start_time": cursor,
                "end_time": end,
                "text": text,
                "confidence": 0.35,
                "source": "fallback",
            }
        )
        cursor = end + 0.8
    return segments


def _average_confidence(tokens: list[dict], default: float) -> float:
    values = [float(token.get("p")) for token in tokens if isinstance(token.get("p"), (int, float))]
    return sum(values) / len(values) if values else default


def _repair_text(value: str) -> str:
    if "Ã" not in value and "Â" not in value:
        return value
    try:
        return value.encode("latin1").decode("utf-8")
    except UnicodeError:
        return value


def _milliseconds_to_seconds(value: str | int | float | None) -> float:
    if value is None:
        return 0.0
    return float(value) / 1000.0


def _timestamp_to_seconds(value: str | int | float | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    parts = value.replace(",", ".").split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return float(value)
