from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.rythmo_layout import build_rythmo
from app.storage.repository import Repository
from app.workers.jobs import JobRunner, register_uploaded_media, save_upload


class ProjectCreate(BaseModel):
    name: str
    language: str = "fr"


class ExportCreate(BaseModel):
    format: str
    options: dict[str, Any] = {}


class PatchPayload(BaseModel):
    text: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    speaker_id: str | None = None
    locked: bool | None = None
    x: float | None = None
    y: float | None = None
    width: float | None = None
    lane: int | None = None

    def clean(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v is not None}


def create_router(repo: Repository, runner: JobRunner) -> APIRouter:
    router = APIRouter(prefix="/api")

    def get_repo() -> Repository:
        return repo

    def get_runner() -> JobRunner:
        return runner

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/projects")
    def create_project(payload: ProjectCreate, repository: Repository = Depends(get_repo)) -> dict:
        return repository.create_project(payload.name, payload.language)

    @router.get("/projects")
    def list_projects(repository: Repository = Depends(get_repo)) -> list[dict]:
        return repository.list_projects()

    @router.get("/projects/{project_id}")
    def get_project(project_id: str, repository: Repository = Depends(get_repo)) -> dict:
        try:
            project = repository.get_project(project_id)
            project["media"] = repository.list_media(project_id)
            return project
        except KeyError:
            raise HTTPException(404, "Projet introuvable") from None

    @router.post("/projects/{project_id}/media")
    def upload_media(
        project_id: str,
        file: UploadFile = File(...),
        autorun: bool = Form(True),
        repository: Repository = Depends(get_repo),
        jobs: JobRunner = Depends(get_runner),
    ) -> dict:
        try:
            repository.get_project(project_id)
            path = save_upload(project_id, file)
            media = register_uploaded_media(repository, project_id, path)
            response = {"media": media}
            if autorun:
                response["job"] = jobs.start_pipeline(project_id)
            return response
        except KeyError:
            raise HTTPException(404, "Projet introuvable") from None

    @router.get("/projects/{project_id}/media")
    def list_media(project_id: str, repository: Repository = Depends(get_repo)) -> list[dict]:
        return repository.list_media(project_id)

    @router.get("/media/{media_id}/file")
    def get_media_file(media_id: str, repository: Repository = Depends(get_repo)) -> FileResponse:
        try:
            media = repository.get_media(media_id)
        except KeyError:
            raise HTTPException(404, "Media introuvable") from None
        path = Path(media["path"])
        if not path.exists():
            raise HTTPException(404, "Fichier media introuvable")
        return FileResponse(path)

    @router.post("/projects/{project_id}/jobs/pipeline")
    def run_pipeline(project_id: str, jobs: JobRunner = Depends(get_runner)) -> dict:
        return jobs.start_pipeline(project_id)

    @router.get("/jobs/{job_id}")
    def get_job(job_id: str, repository: Repository = Depends(get_repo)) -> dict:
        try:
            return repository.get_job(job_id)
        except KeyError:
            raise HTTPException(404, "Job introuvable") from None

    @router.get("/projects/{project_id}/transcript")
    def get_transcript(project_id: str, repository: Repository = Depends(get_repo)) -> dict:
        return repository.get_transcript(project_id)

    @router.patch("/projects/{project_id}/segments/{segment_id}")
    def update_segment(segment_id: str, payload: PatchPayload, repository: Repository = Depends(get_repo)) -> dict:
        try:
            return repository.update_segment(segment_id, payload.clean())
        except KeyError:
            raise HTTPException(404, "Segment introuvable") from None

    @router.patch("/projects/{project_id}/words/{word_id}")
    def update_word(word_id: str, payload: PatchPayload, repository: Repository = Depends(get_repo)) -> dict:
        try:
            return repository.update_word(word_id, payload.clean())
        except KeyError:
            raise HTTPException(404, "Mot introuvable") from None

    @router.get("/projects/{project_id}/rythmo")
    def get_rythmo(project_id: str, repository: Repository = Depends(get_repo)) -> dict:
        return build_rythmo(repository.get_transcript(project_id))

    @router.post("/projects/{project_id}/exports")
    def create_export(project_id: str, payload: ExportCreate, jobs: JobRunner = Depends(get_runner)) -> dict:
        return jobs.start_export(project_id, payload.format.lower(), payload.options)

    @router.get("/projects/{project_id}/exports")
    def list_exports(project_id: str, repository: Repository = Depends(get_repo)) -> list[dict]:
        return repository.list_exports(project_id)

    @router.get("/exports/{export_id}/download")
    def download_export(export_id: str, repository: Repository = Depends(get_repo)) -> FileResponse:
        try:
            export = repository.get_export(export_id)
        except KeyError:
            raise HTTPException(404, "Export introuvable") from None
        if export["status"] != "completed" or not export.get("path"):
            raise HTTPException(409, "Export non pret")
        path = Path(export["path"])
        if not path.exists():
            raise HTTPException(404, "Fichier export introuvable")
        return FileResponse(path, filename=path.name)

    return router

