from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import keyring

APP_NAME = "OpenReelAI"


def app_data_dir() -> Path:
    base = Path(os.getenv("APPDATA", Path.home()))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(slots=True)
class Settings:
    render_mode: str = "public_assets"
    video_provider: str = "replicate"
    video_model: str = "kwaivgi/kling-v2.1"
    hf_endpoint: str = "https://router.huggingface.co/hf-inference/models"
    planner_base_url: str = "https://api.openai.com/v1"
    planner_model: str = "gpt-4.1-mini"
    width: int = 1280
    height: int = 720
    fps: int = 24
    output_dir: str = str(Path.home() / "Videos" / "OpenReel")
    cleanup_downloads: bool = True

    @classmethod
    def load(cls) -> "Settings":
        path = app_data_dir() / "settings.json"
        if not path.exists():
            return cls()
        try:
            values = json.loads(path.read_text(encoding="utf-8"))
            allowed = cls.__dataclass_fields__.keys()
            return cls(**{key: value for key, value in values.items() if key in allowed})
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self) -> None:
        (app_data_dir() / "settings.json").write_text(
            json.dumps(asdict(self), indent=2), encoding="utf-8"
        )


def get_secret(name: str) -> str:
    return keyring.get_password(APP_NAME, name) or ""


def set_secret(name: str, value: str) -> None:
    if value:
        keyring.set_password(APP_NAME, name, value)
    else:
        try:
            keyring.delete_password(APP_NAME, name)
        except keyring.errors.PasswordDeleteError:
            pass
