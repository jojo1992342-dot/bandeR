from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.database import Database
from app.core.utils import json_dumps, json_loads, new_id, utc_now


def row_to_dict(row: Any) -> dict[str, Any]:
    data = dict(row)
    for key in ("settings_json", "result_json"):
        if key in data:
            data[key.replace("_json", "")] = json_loads(data.pop(key))
    return data


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_project(self, name: str, language: str = "fr") -> dict[str, Any]:
        project_id = new_id("prj")
        now = utc_now()
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO projects (id, name, language, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (project_id, name, language, now, now),
            )
            speaker_id = new_id("spk")
            conn.execute(
                """
                INSERT INTO speakers (id, project_id, name, color, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (speaker_id, project_id, "Voix 1", "#2f80ed", now),
            )
        return self.get_project(project_id)

    def list_projects(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
        return [row_to_dict(row) for row in rows]

    def get_project(self, project_id: str) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            raise KeyError(project_id)
        return row_to_dict(row)

    def update_project_status(
        self,
        project_id: str,
        status: str,
        duration: float | None = None,
        frame_rate: float | None = None,
    ) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE projects
                SET status = ?, duration = COALESCE(?, duration), frame_rate = COALESCE(?, frame_rate), updated_at = ?
                WHERE id = ?
                """,
                (status, duration, frame_rate, utc_now(), project_id),
            )

    def add_media(
        self,
        project_id: str,
        kind: str,
        path: Path,
        metadata: dict[str, Any] | None = None,
        file_hash: str | None = None,
    ) -> dict[str, Any]:
        metadata = metadata or {}
        media_id = new_id("med")
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO media_assets (id, project_id, kind, path, duration, fps, width, height, codec, hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    media_id,
                    project_id,
                    kind,
                    str(path),
                    metadata.get("duration"),
                    metadata.get("fps"),
                    metadata.get("width"),
                    metadata.get("height"),
                    metadata.get("codec"),
                    file_hash,
                    utc_now(),
                ),
            )
        return self.get_media(media_id)

    def get_media(self, media_id: str) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM media_assets WHERE id = ?", (media_id,)).fetchone()
        if row is None:
            raise KeyError(media_id)
        return row_to_dict(row)

    def list_media(self, project_id: str) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM media_assets WHERE project_id = ? ORDER BY created_at",
                (project_id,),
            ).fetchall()
        return [row_to_dict(row) for row in rows]

    def get_media_by_kind(self, project_id: str, kind: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM media_assets
                WHERE project_id = ? AND kind = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (project_id, kind),
            ).fetchone()
        return row_to_dict(row) if row else None

    def get_default_speaker(self, project_id: str) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM speakers WHERE project_id = ? ORDER BY created_at LIMIT 1",
                (project_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"No speaker for {project_id}")
        return row_to_dict(row)

    def replace_transcript(self, project_id: str, segments: list[dict[str, Any]]) -> None:
        now = utc_now()
        speaker = self.get_default_speaker(project_id)
        with self.db.connect() as conn:
            old_segments = conn.execute(
                "SELECT id FROM segments WHERE project_id = ? AND locked = 0",
                (project_id,),
            ).fetchall()
            for row in old_segments:
                conn.execute("DELETE FROM words WHERE segment_id = ?", (row["id"],))
            conn.execute("DELETE FROM segments WHERE project_id = ? AND locked = 0", (project_id,))
            for seg in segments:
                segment_id = seg.get("id") or new_id("seg")
                conn.execute(
                    """
                    INSERT INTO segments
                    (id, project_id, speaker_id, start_time, end_time, text, confidence, source, locked, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        segment_id,
                        project_id,
                        seg.get("speaker_id") or speaker["id"],
                        float(seg["start_time"]),
                        float(seg["end_time"]),
                        seg["text"],
                        float(seg.get("confidence", 0.75)),
                        seg.get("source", "asr"),
                        int(bool(seg.get("locked", False))),
                        now,
                        now,
                    ),
                )
                for idx, word in enumerate(seg.get("words", [])):
                    conn.execute(
                        """
                        INSERT INTO words
                        (id, segment_id, idx, text, normalized_text, start_time, end_time, confidence, x, y, width, lane, locked)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            word.get("id") or new_id("wrd"),
                            segment_id,
                            idx,
                            word["text"],
                            word.get("normalized_text", word["text"].lower()),
                            float(word["start_time"]),
                            float(word["end_time"]),
                            float(word.get("confidence", seg.get("confidence", 0.75))),
                            float(word.get("x", 0)),
                            float(word.get("y", 0)),
                            float(word.get("width", 0)),
                            int(word.get("lane", 0)),
                            int(bool(word.get("locked", False))),
                        ),
                    )

    def get_transcript(self, project_id: str) -> dict[str, Any]:
        with self.db.connect() as conn:
            seg_rows = conn.execute(
                """
                SELECT s.*, sp.name AS speaker_name, sp.color AS speaker_color
                FROM segments s
                LEFT JOIN speakers sp ON sp.id = s.speaker_id
                WHERE s.project_id = ?
                ORDER BY s.start_time, s.end_time
                """,
                (project_id,),
            ).fetchall()
            segments = []
            for seg in seg_rows:
                words = conn.execute(
                    "SELECT * FROM words WHERE segment_id = ? ORDER BY idx",
                    (seg["id"],),
                ).fetchall()
                item = row_to_dict(seg)
                item["words"] = [row_to_dict(word) for word in words]
                segments.append(item)
        return {"project_id": project_id, "segments": segments}

    def update_segment(self, segment_id: str, data: dict[str, Any]) -> dict[str, Any]:
        allowed = {k: data[k] for k in ["text", "start_time", "end_time", "speaker_id", "locked"] if k in data}
        if not allowed:
            return self.get_segment(segment_id)
        sets = ", ".join(f"{key} = ?" for key in allowed)
        values = [int(v) if isinstance(v, bool) else v for v in allowed.values()]
        with self.db.connect() as conn:
            conn.execute(
                f"UPDATE segments SET {sets}, updated_at = ? WHERE id = ?",
                (*values, utc_now(), segment_id),
            )
        return self.get_segment(segment_id)

    def update_word(self, word_id: str, data: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            k: data[k]
            for k in ["text", "start_time", "end_time", "x", "y", "width", "lane", "locked"]
            if k in data
        }
        if "text" in allowed:
            allowed["normalized_text"] = str(allowed["text"]).lower()
        if not allowed:
            return self.get_word(word_id)
        sets = ", ".join(f"{key} = ?" for key in allowed)
        values = [int(v) if isinstance(v, bool) else v for v in allowed.values()]
        with self.db.connect() as conn:
            conn.execute(f"UPDATE words SET {sets} WHERE id = ?", (*values, word_id))
        return self.get_word(word_id)

    def get_segment(self, segment_id: str) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM segments WHERE id = ?", (segment_id,)).fetchone()
        if row is None:
            raise KeyError(segment_id)
        return row_to_dict(row)

    def get_word(self, word_id: str) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM words WHERE id = ?", (word_id,)).fetchone()
        if row is None:
            raise KeyError(word_id)
        return row_to_dict(row)

    def create_job(self, kind: str, project_id: str | None = None) -> dict[str, Any]:
        job_id = new_id("job")
        now = utc_now()
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, project_id, kind, status, created_at, updated_at)
                VALUES (?, ?, ?, 'queued', ?, ?)
                """,
                (job_id, project_id, kind, now, now),
            )
        return self.get_job(job_id)

    def update_job(
        self,
        job_id: str,
        status: str | None = None,
        progress: float | None = None,
        stage: str | None = None,
        message: str | None = None,
        error: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fields: dict[str, Any] = {"updated_at": utc_now()}
        if status is not None:
            fields["status"] = status
        if progress is not None:
            fields["progress"] = progress
        if stage is not None:
            fields["stage"] = stage
        if message is not None:
            fields["message"] = message
        if error is not None:
            fields["error"] = error
        if result is not None:
            fields["result_json"] = json_dumps(result)
        sets = ", ".join(f"{key} = ?" for key in fields)
        with self.db.connect() as conn:
            conn.execute(f"UPDATE jobs SET {sets} WHERE id = ?", (*fields.values(), job_id))
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return row_to_dict(row)

    def create_export(self, project_id: str, fmt: str, settings: dict[str, Any]) -> dict[str, Any]:
        export_id = new_id("exp")
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO exports (id, project_id, format, status, settings_json, created_at)
                VALUES (?, ?, ?, 'running', ?, ?)
                """,
                (export_id, project_id, fmt, json_dumps(settings), utc_now()),
            )
        return self.get_export(export_id)

    def complete_export(self, export_id: str, path: Path | None, error: str | None = None) -> dict[str, Any]:
        status = "failed" if error else "completed"
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE exports SET status = ?, path = ?, error = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, str(path) if path else None, error, utc_now(), export_id),
            )
        return self.get_export(export_id)

    def get_export(self, export_id: str) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM exports WHERE id = ?", (export_id,)).fetchone()
        if row is None:
            raise KeyError(export_id)
        return row_to_dict(row)

    def list_exports(self, project_id: str) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exports WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        return [row_to_dict(row) for row in rows]

