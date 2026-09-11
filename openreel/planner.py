from __future__ import annotations

import json
import math
import re

import requests

from .models import ProjectPlan, Scene


SYSTEM_PROMPT = """You are a film director. Return strict JSON only with keys title,
style_bible, and scenes. Each scene has visual_prompt and narration. Maintain exact
character, wardrobe, environment and cinematic continuity. Prompts must describe motion,
camera movement, lighting, composition and subject. Do not include scene numbers in prompts.
The requested scene count must be exact."""


def _extract_json(value: str) -> dict:
    value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value.strip(), flags=re.I)
    return json.loads(value)


class Planner:
    def __init__(self, base_url: str, model: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    def plan(self, prompt: str, duration: int, clip_seconds: int = 5) -> ProjectPlan:
        scene_count = math.ceil(duration / clip_seconds)
        if not self.api_key:
            return self._local_plan(prompt, duration, clip_seconds)
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Create {scene_count} scenes of {clip_seconds} seconds for this "
                            f"video concept: {prompt}"
                        ),
                    },
                ],
            },
            timeout=120,
        )
        response.raise_for_status()
        data = _extract_json(response.json()["choices"][0]["message"]["content"])
        raw_scenes = data.get("scenes", [])
        if len(raw_scenes) != scene_count:
            raise ValueError(f"Planner returned {len(raw_scenes)} scenes; expected {scene_count}")
        scenes = [
            Scene(
                index=i + 1,
                duration=min(clip_seconds, duration - i * clip_seconds),
                visual_prompt=item["visual_prompt"],
                narration=item.get("narration", ""),
            )
            for i, item in enumerate(raw_scenes)
        ]
        return ProjectPlan(data.get("title", "Untitled"), data.get("style_bible", ""), scenes)

    @staticmethod
    def _local_plan(prompt: str, duration: int, clip_seconds: int) -> ProjectPlan:
        count = math.ceil(duration / clip_seconds)
        style = "cinematic continuity, realistic motion, coherent subjects, 16:9 composition"
        scenes = []
        shot_types = ["wide establishing shot", "medium tracking shot", "close detail shot"]
        for i in range(count):
            phase = (i + 1) / count
            scenes.append(
                Scene(
                    index=i + 1,
                    duration=min(clip_seconds, duration - i * clip_seconds),
                    visual_prompt=(
                        f"{prompt}. {shot_types[i % len(shot_types)]}, story progression "
                        f"{phase:.0%}, natural physical movement, cinematic lighting, {style}"
                    ),
                )
            )
        return ProjectPlan(prompt[:60] or "Untitled", style, scenes)
