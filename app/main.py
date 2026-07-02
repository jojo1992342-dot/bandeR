from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import ensure_directories, settings
from app.core.database import Database
from app.storage.repository import Repository
from app.workers.jobs import JobRunner
from app.api.routes import create_router


ensure_directories()
database = Database(settings.db_path)
database.init()
repository = Repository(database)
job_runner = JobRunner(repository)

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(create_router(repository, job_runner))

frontend_dir = settings.base_dir / "frontend"
assets_dir = frontend_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")


@app.post("/api/system/restart")
def restart_server(request: Request) -> dict[str, str]:
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "localhost"}:
        return {"status": "refused"}

    def restart() -> None:
        time.sleep(0.4)
        if os.name == "nt":
            command = f'timeout /t 2 /nobreak >nul && "{sys.executable}" -m app.main'
            subprocess.Popen(
                ["cmd", "/c", command],
                cwd=str(settings.base_dir),
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        else:
            command = f'sleep 2 && "{sys.executable}" -m app.main'
            subprocess.Popen(["sh", "-c", command], cwd=str(settings.base_dir))
        os._exit(0)

    threading.Thread(target=restart, daemon=True).start()
    return {"status": "restarting"}


@app.websocket("/ws/projects/{project_id}")
async def project_socket(websocket: WebSocket, project_id: str) -> None:
    await websocket.accept()
    last_payload = None
    try:
        while True:
            projects = repository.get_project(project_id)
            transcript = repository.get_transcript(project_id)
            payload = {"type": "project.snapshot", "project": projects, "segments": len(transcript["segments"])}
            if payload != last_payload:
                await websocket.send_json(payload)
                last_payload = payload
            await asyncio.sleep(1.0)
    except (WebSocketDisconnect, KeyError):
        return


def main() -> None:
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()

