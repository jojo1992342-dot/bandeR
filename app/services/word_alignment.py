from __future__ import annotations

import re

WORD_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def align_words(segments: list[dict], media_duration: float | None = None) -> list[dict]:
    normalized = _normalize_segment_times(segments, media_duration)
    aligned = []
    for seg in normalized:
        if seg.get("words"):
            item = dict(seg)
            item["words"] = _normalize_existing_words(seg["words"], float(seg["start_time"]), float(seg["end_time"]))
            aligned.append(item)
            continue
        words = WORD_RE.findall(seg["text"])
        if not words:
            seg["words"] = []
            aligned.append(seg)
            continue
        start = float(seg["start_time"])
        end = max(float(seg["end_time"]), start + 0.1)
        weights = [max(0.35, len(word.strip()) * 0.18) for word in words]
        total = sum(weights)
        cursor = start
        timed_words = []
        for idx, word in enumerate(words):
            dur = (end - start) * (weights[idx] / total)
            word_start = cursor
            word_end = end if idx == len(words) - 1 else min(end, cursor + dur)
            timed_words.append(
                {
                    "text": word,
                    "normalized_text": word.lower(),
                    "start_time": round(word_start, 3),
                    "end_time": round(max(word_end, word_start + 0.04), 3),
                    "confidence": min(float(seg.get("confidence", 0.6)), 0.65),
                }
            )
            cursor = word_end
        item = dict(seg)
        item["words"] = timed_words
        aligned.append(item)
    return aligned


def _normalize_existing_words(words: list[dict], segment_start: float, segment_end: float) -> list[dict]:
    max_time = max(float(word.get("end_time", 0) or 0) for word in words) if words else 0
    factor = 1000.0 if max_time > max(segment_end * 5, 1000.0) else 1.0
    cleaned = []
    previous_end = segment_start
    for word in words:
        text = str(word.get("text", "")).strip()
        if not text:
            continue
        start = max(segment_start, float(word.get("start_time", segment_start)) / factor, previous_end)
        end = min(segment_end, max(float(word.get("end_time", start + 0.04)) / factor, start + 0.04))
        cleaned.append(
            {
                "text": text,
                "normalized_text": str(word.get("normalized_text", text.lower())),
                "start_time": round(start, 3),
                "end_time": round(end, 3),
                "confidence": float(word.get("confidence", 0.75)),
            }
        )
        previous_end = end
    return cleaned


def _normalize_segment_times(segments: list[dict], media_duration: float | None) -> list[dict]:
    if not segments:
        return segments
    max_time = max(float(seg.get("end_time", 0) or 0) for seg in segments)
    duration = float(media_duration or 0)
    looks_like_ms = max_time > 1000 or (duration > 0 and max_time > duration * 5)
    if not looks_like_ms:
        return segments
    fixed = []
    for seg in segments:
        item = dict(seg)
        item["start_time"] = float(item["start_time"]) / 1000.0
        item["end_time"] = float(item["end_time"]) / 1000.0
        if item.get("words"):
            fixed_words = []
            for word in item["words"]:
                fixed_word = dict(word)
                fixed_word["start_time"] = float(fixed_word["start_time"]) / 1000.0
                fixed_word["end_time"] = float(fixed_word["end_time"]) / 1000.0
                fixed_words.append(fixed_word)
            item["words"] = fixed_words
        fixed.append(item)
    return fixed
