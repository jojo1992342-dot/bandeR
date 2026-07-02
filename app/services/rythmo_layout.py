from __future__ import annotations


DEFAULT_LAYOUT = {
    "pixels_per_second": 180,
    "font_size": 28,
    "lane_height": 56,
    "safe_left": 360,
    "baseline": 96,
}


def build_rythmo(transcript: dict, settings: dict | None = None) -> dict:
    cfg = {**DEFAULT_LAYOUT, **(settings or {})}
    items = []
    for seg_index, segment in enumerate(transcript.get("segments", [])):
        lane = seg_index % 3
        for word in segment.get("words", []):
            start = float(word["start_time"])
            end = float(word["end_time"])
            width = max(28, (end - start) * cfg["pixels_per_second"])
            items.append(
                {
                    "id": word["id"],
                    "segment_id": segment["id"],
                    "text": word["text"],
                    "start_time": start,
                    "end_time": end,
                    "x": start * cfg["pixels_per_second"],
                    "y": cfg["baseline"] + lane * cfg["lane_height"],
                    "width": width,
                    "lane": lane,
                    "speaker": segment.get("speaker_name") or "Voix",
                    "color": segment.get("speaker_color") or "#2f80ed",
                    "confidence": word.get("confidence", 0),
                }
            )
    return {"settings": cfg, "items": items}

