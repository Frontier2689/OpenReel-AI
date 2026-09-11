from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urlparse

import requests


class ProviderError(RuntimeError):
    pass


def _download(url: str, destination: Path) -> None:
    with requests.get(url, stream=True, timeout=300) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_content(1024 * 1024):
                handle.write(chunk)


class ReplicateProvider:
    api_root = "https://api.replicate.com/v1"

    def __init__(self, token: str, model: str):
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self.model = model.strip("/")

    def generate(self, prompt: str, seconds: int, destination: Path) -> None:
        url = f"{self.api_root}/models/{self.model}/predictions"
        response = requests.post(
            url,
            headers={**self.headers, "Prefer": "wait=5"},
            json={"input": {"prompt": prompt, "duration": seconds, "aspect_ratio": "16:9"}},
            timeout=30,
        )
        response.raise_for_status()
        prediction = response.json()
        while prediction.get("status") not in {"succeeded", "failed", "canceled"}:
            time.sleep(2)
            response = requests.get(prediction["urls"]["get"], headers=self.headers, timeout=30)
            response.raise_for_status()
            prediction = response.json()
        if prediction.get("status") != "succeeded":
            raise ProviderError(prediction.get("error") or f"Prediction {prediction.get('status')}")
        output = prediction.get("output")
        if isinstance(output, list):
            output = output[0]
        if isinstance(output, dict):
            output = output.get("url") or output.get("video")
        if not isinstance(output, str) or urlparse(output).scheme not in {"http", "https"}:
            raise ProviderError("Provider did not return a downloadable video URL")
        _download(output, destination)


class HuggingFaceProvider:
    def __init__(self, token: str, model: str, endpoint: str):
        self.token = token
        self.model = model.strip("/")
        self.endpoint = endpoint.rstrip("/")

    def generate(self, prompt: str, seconds: int, destination: Path) -> None:
        response = requests.post(
            f"{self.endpoint}/{self.model}",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"inputs": prompt, "parameters": {"num_frames": max(16, seconds * 16)}},
            timeout=600,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = response.json()
            url = payload.get("url") if isinstance(payload, dict) else None
            if not url:
                raise ProviderError(str(payload))
            _download(url, destination)
        else:
            destination.write_bytes(response.content)


def make_provider(name: str, token: str, model: str, hf_endpoint: str):
    if not token:
        raise ProviderError(f"An API token is required for {name}")
    if name == "replicate":
        return ReplicateProvider(token, model)
    if name == "huggingface":
        return HuggingFaceProvider(token, model, hf_endpoint)
    raise ProviderError(f"Unknown provider: {name}")
