from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Callable

from . import ffmpeg
from .assets import AssetError, PublicCatalogs
from .config import Settings, get_secret
from .planner import Planner
from .providers import make_provider

Progress = Callable[[float, str], None]


def _slug(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")
    return clean[:50] or "video"


class Pipeline:
    def __init__(self, settings: Settings, cancel_event: threading.Event, progress: Progress):
        self.settings = settings
        self.cancel_event = cancel_event
        self.progress = progress

    def run(self, prompt: str, duration: int) -> Path:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        project = Path(self.settings.output_dir) / f"{timestamp}-{_slug(prompt)}"
        raw_dir, clip_dir = project / "raw", project / "clips"
        raw_dir.mkdir(parents=True, exist_ok=True)
        clip_dir.mkdir(parents=True, exist_ok=True)

        self.progress(0.01, "Planning scenes…")
        planner = Planner(
            self.settings.planner_base_url,
            self.settings.planner_model,
            get_secret("planner_token"),
        )
        plan = planner.plan(prompt, duration)
        (project / "project.json").write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
        provider = None
        catalog = None
        if self.settings.render_mode == "public_assets":
            catalog = PublicCatalogs(get_secret("pexels_token"))
        else:
            token_name = f"{self.settings.video_provider}_token"
            provider = make_provider(
                self.settings.video_provider,
                get_secret(token_name),
                self.settings.video_model,
                self.settings.hf_endpoint,
            )
        completed = []
        sources = []
        for position, scene in enumerate(plan.scenes):
            self._check_cancel()
            clip = clip_dir / f"scene-{scene.index:03d}.mp4"
            overall_prompt = f"{plan.style_bible}. {scene.visual_prompt}"
            raw = None
            if catalog:
                self.progress(position / len(plan.scenes), f"Finding media for scene {scene.index}/{len(plan.scenes)}…")
                assets = catalog.search(scene.visual_prompt)
                if not assets:
                    raise AssetError(f"No reusable Wikimedia Commons media found for: {scene.visual_prompt}")
                asset = assets[position % len(assets)]
                raw = raw_dir / f"scene-{scene.index:03d}{asset.extension}"
                if not raw.exists() or raw.stat().st_size == 0:
                    catalog.download(asset, raw)
                if asset.media_type == "video":
                    ffmpeg.normalize(raw, clip, scene.duration, self.settings.width, self.settings.height, self.settings.fps)
                else:
                    ffmpeg.animate_image(raw, clip, scene.duration, self.settings.width, self.settings.height, self.settings.fps, scene.index)
                source = asset.to_dict()
                source["scene"] = scene.index
                sources.append(source)
            else:
                raw = raw_dir / f"scene-{scene.index:03d}.mp4"
                if not raw.exists() or raw.stat().st_size == 0:
                    self.progress(position / len(plan.scenes), f"Generating scene {scene.index}/{len(plan.scenes)}…")
                    provider.generate(overall_prompt, scene.duration, raw)
                self._check_cancel()
                if not clip.exists() or clip.stat().st_size == 0:
                    ffmpeg.normalize(raw, clip, scene.duration, self.settings.width, self.settings.height, self.settings.fps)
            completed.append(clip)

        self.progress(0.97, "Joining clips…")
        output = project / f"{_slug(plan.title)}.mp4"
        ffmpeg.concatenate(completed, output)
        if sources:
            (project / "sources.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
        if self.settings.cleanup_downloads:
            for downloaded in raw_dir.iterdir():
                if downloaded.is_file():
                    downloaded.unlink()
        self.progress(1.0, f"Finished: {output}")
        return output

    def _check_cancel(self):
        if self.cancel_event.is_set():
            raise InterruptedError("Generation canceled")
