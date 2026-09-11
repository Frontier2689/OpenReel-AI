from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class Scene:
    index: int
    duration: int
    visual_prompt: str
    narration: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ProjectPlan:
    title: str
    style_bible: str
    scenes: list[Scene]

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "style_bible": self.style_bible,
            "scenes": [scene.to_dict() for scene in self.scenes],
        }
