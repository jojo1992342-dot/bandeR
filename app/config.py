from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


def _resolve_binary(env_name: str, default_name: str, known_paths: tuple[str, ...] = ()) -> str:
    configured = os.getenv(env_name)
    if configured:
        return configured
    found = shutil.which(default_name)
    if found:
        return found
    for candidate in known_paths:
        if Path(candidate).exists():
            return candidate
    return default_name


@dataclass(frozen=True)
class Settings:
    app_name: str = "Bande Rythmo Local Studio"
    host: str = "127.0.0.1"
    port: int = 8000
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = Path(os.getenv("BR_DATA_DIR", "data"))
    ffmpeg_bin: str = _resolve_binary(
        "FFMPEG_BIN",
        "ffmpeg",
        (r"C:\Users\Jonathan\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe",),
    )
    ffprobe_bin: str = _resolve_binary(
        "FFPROBE_BIN",
        "ffprobe",
        (r"C:\Users\Jonathan\AppData\Local\Microsoft\WinGet\Links\ffprobe.exe",),
    )
    whisper_cpp_bin: str | None = os.getenv("WHISPER_CPP_BIN")
    whisper_model: str | None = os.getenv("WHISPER_MODEL")
    llama_cpp_bin: str | None = os.getenv("LLAMA_CPP_BIN")
    llama_model: str | None = os.getenv("LLAMA_MODEL")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "bande_rythmo.sqlite3"

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def temp_dir(self) -> Path:
        return self.data_dir / "temp"


settings = Settings()


def ensure_directories() -> None:
    for path in [
        settings.data_dir,
        settings.projects_dir,
        settings.exports_dir,
        settings.temp_dir,
        settings.data_dir / "models",
    ]:
        path.mkdir(parents=True, exist_ok=True)
