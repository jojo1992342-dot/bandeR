from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import Callable

from fastapi import UploadFile

from app.config import settings
from app.core.utils import file_sha256
from app.services.audio_extraction import extract_audio_for_asr
from app.services.exporters import export_ass, export_json, export_srt, export_video_with_rythmo, export_vtt, export_xml
from app.services.media_probe import probe_media
from app.services.rythmo_layout import build_rythmo
from app.services.speech_recognition import transcribe_audio
from app.services.word_alignment import align_words
from app.storage.repository import Repository


class JobRunner:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def start_pipeline(self, project_id: str) -> dict:
        job = self.repo.create_job("full_pipeline", project_id)
        thread = threading.Thread(target=self._run_pipeline, args=(job["id"], project_id), daemon=True)
        thread.start()
        return job

    def start_export(self, project_id: str, fmt: str, options: dict) -> dict:
        job = self.repo.create_job(f"export_{fmt}", project_id)
        thread = threading.Thread(target=self._run_export, args=(job["id"], project_id, fmt, options), daemon=True)
        thread.start()
        return job

    def _run_pipeline(self, job_id: str, project_id: str) -> None:
        try:
            self._progress(job_id, 0.05, "probe", "Analyse du media source")
            source = self.repo.get_media_by_kind(project_id, "source")
            if not source:
                raise RuntimeError("Aucun media source associe au projet")
            source_path = Path(source["path"])
            metadata = probe_media(source_path)
            self.repo.update_project_status(project_id, "media_ready", metadata.get("duration"), metadata.get("fps"))

            self._progress(job_id, 0.22, "audio", "Extraction audio pour ASR")
            project_dir = settings.projects_dir / project_id
            audio_path = project_dir / "audio" / "audio_asr.wav"
            try:
                extract_audio_for_asr(source_path, audio_path)
                self.repo.add_media(project_id, "audio_asr", audio_path, {"duration": metadata.get("duration")})
            except RuntimeError as exc:
                self._progress(job_id, 0.30, "audio_skipped", str(exc))

            self._progress(job_id, 0.48, "asr", "Reconnaissance vocale locale")
            audio_for_asr = audio_path if audio_path.exists() else None
            segments = transcribe_audio(audio_for_asr, metadata.get("duration"), self.repo.get_project(project_id)["language"])

            self._progress(job_id, 0.68, "alignment", "Alignement temporel des mots")
            aligned = align_words(segments, metadata.get("duration"))
            self.repo.replace_transcript(project_id, aligned)

            self._progress(job_id, 0.86, "rythmo", "Generation de la bande rythmo")
            transcript = self.repo.get_transcript(project_id)
            build_rythmo(transcript)
            self.repo.update_project_status(project_id, "ready")

            self.repo.update_job(
                job_id,
                status="completed",
                progress=1,
                stage="done",
                message="Pipeline termine",
                result={"project_id": project_id},
            )
        except Exception as exc:
            self.repo.update_project_status(project_id, "error")
            self.repo.update_job(job_id, status="failed", stage="error", message="Echec du pipeline", error=str(exc))

    def _run_export(self, job_id: str, project_id: str, fmt: str, options: dict) -> None:
        export = self.repo.create_export(project_id, fmt, options)
        try:
            self._progress(job_id, 0.25, "prepare", "Preparation export")
            project = self.repo.get_project(project_id)
            transcript = self.repo.get_transcript(project_id)
            rythmo = build_rythmo(transcript, options.get("layout"))
            out_dir = settings.exports_dir / project_id
            base = out_dir / f"{project['name'].replace(' ', '_')}_{export['id']}"
            handlers: dict[str, Callable[[Path], Path]] = {
                "json": lambda path: export_json(project, transcript, rythmo, path.with_suffix(".json")),
                "xml": lambda path: export_xml(project, transcript, path.with_suffix(".xml")),
                "srt": lambda path: export_srt(transcript, path.with_suffix(".srt")),
                "vtt": lambda path: export_vtt(transcript, path.with_suffix(".vtt")),
                "ass": lambda path: export_ass(transcript, path.with_suffix(".ass")),
                "mp4": lambda path: export_video_with_rythmo(Path(self.repo.get_media_by_kind(project_id, "source")["path"]), transcript, path.with_suffix(".mp4")),
                "video": lambda path: export_video_with_rythmo(Path(self.repo.get_media_by_kind(project_id, "source")["path"]), transcript, path.with_suffix(".mp4")),
            }
            if fmt not in handlers:
                raise RuntimeError(f"Format export non supporte: {fmt}")
            self._progress(job_id, 0.70, "write", f"Ecriture {fmt.upper()}")
            output = handlers[fmt](base)
            self.repo.complete_export(export["id"], output)
            self.repo.update_job(
                job_id,
                status="completed",
                progress=1,
                stage="done",
                message="Export termine",
                result={"export_id": export["id"], "path": str(output)},
            )
        except Exception as exc:
            self.repo.complete_export(export["id"], None, str(exc))
            self.repo.update_job(job_id, status="failed", progress=1, stage="error", message="Echec export", error=str(exc))

    def _progress(self, job_id: str, progress: float, stage: str, message: str) -> None:
        self.repo.update_job(job_id, status="running", progress=progress, stage=stage, message=message)


def save_upload(project_id: str, upload: UploadFile) -> Path:
    project_dir = settings.projects_dir / project_id / "source"
    project_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(upload.filename or "source.mp4").name
    output = project_dir / safe_name
    with output.open("wb") as fh:
        shutil.copyfileobj(upload.file, fh)
    return output


def register_uploaded_media(repo: Repository, project_id: str, path: Path) -> dict:
    metadata = probe_media(path)
    digest = file_sha256(path, limit_bytes=128 * 1024 * 1024)
    media = repo.add_media(project_id, "source", path, metadata, digest)
    repo.update_project_status(project_id, "imported", metadata.get("duration"), metadata.get("fps"))
    return media





