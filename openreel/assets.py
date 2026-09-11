from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "OpenReelAI/0.2 (public-media video composer)"


class AssetError(RuntimeError):
    pass


def _plain(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("value", "")
    return html.unescape(re.sub(r"<[^>]+>", "", str(value))).strip()


def compact_query(prompt: str) -> str:
    """Turn a cinematic scene prompt into a useful repository search."""
    first_clause = re.split(r"[.;]", prompt, maxsplit=1)[0]
    noise = {
        "create", "video", "cinematic", "realistic", "motion", "shot", "camera",
        "lighting", "composition", "natural", "physical", "movement", "wide",
        "medium", "close", "tracking", "establishing", "detail", "hello",
        "a", "an", "the", "of", "with", "and",
    }
    words = re.findall(r"[A-Za-z0-9'-]+", first_clause.lower())
    useful = [word for word in words if word not in noise]
    normalized = ["woman" if word == "girl" else word for word in useful[:10]]
    return " ".join(normalized) or first_clause.strip() or prompt.strip()


@dataclass(slots=True)
class MediaAsset:
    source: str
    title: str
    url: str
    page_url: str
    mime: str
    media_type: str
    creator: str
    license: str
    license_url: str
    attribution: str

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def extension(self) -> str:
        suffix = Path(urlparse(self.url).path).suffix.lower()
        return suffix if suffix and len(suffix) <= 6 else ".bin"


class WikimediaCommons:
    """Search and retrieve openly licensed media from Wikimedia Commons."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._cache: dict[str, list[MediaAsset]] = {}

    def search(self, prompt: str, limit: int = 20) -> list[MediaAsset]:
        query = compact_query(prompt)
        if query in self._cache:
            return self._cache[query]
        video_pages = self._search_pages(f"{query} filetype:video", max(5, limit // 2))
        image_pages = self._search_pages(f"{query} filetype:bitmap", limit)
        if not video_pages and not image_pages:
            # Descriptive traits can be too restrictive for repository metadata.
            simplified = " ".join(
                word for word in query.split()
                if word not in {"blonde", "blond", "brunette", "young", "older"}
            )
            video_pages = self._search_pages(f"{simplified} filetype:video", max(5, limit // 2))
            image_pages = self._search_pages(f"{simplified} filetype:bitmap", limit)
        pages = video_pages + image_pages
        assets: list[MediaAsset] = []
        allow_mature = any(
            term in prompt.casefold()
            for term in ("nude", "nudist", "naked", "erotic", "sexual", "adult content")
        )
        for page in pages:
            title_text = page.get("title", "").casefold()
            if not allow_mature and any(
                term in title_text for term in ("nude", "nudist", "naked", "porn", "erotic")
            ):
                continue
            info = (page.get("imageinfo") or [{}])[0]
            mime = info.get("mime", "")
            if not (mime.startswith("video/") or mime.startswith("image/")):
                continue
            meta = info.get("extmetadata", {})
            asset = MediaAsset(
                source="Wikimedia Commons",
                title=page.get("title", "Untitled"),
                url=info.get("url", ""),
                page_url=info.get("descriptionurl", ""),
                mime=mime,
                media_type="video" if mime.startswith("video/") else "image",
                creator=_plain(meta.get("Artist")),
                license=_plain(meta.get("LicenseShortName")) or "See source page",
                license_url=_plain(meta.get("LicenseUrl")),
                attribution=_plain(meta.get("Credit")) or _plain(meta.get("Attribution")),
            )
            if asset.url.startswith("https://"):
                assets.append(asset)
        assets.sort(key=lambda item: (item.media_type != "video", item.title.casefold()))
        self._cache[query] = assets
        return assets

    def _search_pages(self, query: str, limit: int) -> list[dict]:
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": "6",
            "gsrlimit": str(min(limit, 50)),
            "prop": "imageinfo",
            "iiprop": "url|mime|mediatype|extmetadata",
            "origin": "*",
        }
        response = self.session.get(COMMONS_API, params=params, timeout=45)
        response.raise_for_status()
        return response.json().get("query", {}).get("pages", [])

    def download(self, asset: MediaAsset, destination: Path) -> None:
        with self.session.get(asset.url, stream=True, timeout=180) as response:
            response.raise_for_status()
            with destination.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        if destination.stat().st_size == 0:
            raise AssetError("The selected Commons asset was empty")


class PublicCatalogs:
    """Search free stock media first, then the no-key Commons catalog."""

    def __init__(self, pexels_token: str = ""):
        self.pexels_token = pexels_token
        self.commons = WikimediaCommons()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def search(self, prompt: str, limit: int = 20) -> list[MediaAsset]:
        if self.pexels_token:
            results = self._pexels(compact_query(prompt), limit)
            if results:
                return results
        return self.commons.search(prompt, limit)

    def download(self, asset: MediaAsset, destination: Path) -> None:
        with self.session.get(asset.url, stream=True, timeout=180) as response:
            response.raise_for_status()
            with destination.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        if destination.stat().st_size == 0:
            raise AssetError("The selected public asset was empty")

    def _pexels(self, query: str, limit: int) -> list[MediaAsset]:
        headers = {"Authorization": self.pexels_token}
        response = self.session.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params={"query": query, "per_page": min(limit, 40), "orientation": "landscape"},
            timeout=45,
        )
        response.raise_for_status()
        assets = []
        for video in response.json().get("videos", []):
            files = [item for item in video.get("video_files", []) if item.get("link")]
            if not files:
                continue
            files.sort(key=lambda item: (item.get("width", 0) > 1920, -item.get("width", 0)))
            selected = files[0]
            user = video.get("user", {})
            assets.append(MediaAsset(
                source="Pexels",
                title=f"Pexels video {video.get('id', '')}",
                url=selected["link"],
                page_url=video.get("url", ""),
                mime=selected.get("file_type", "video/mp4"),
                media_type="video",
                creator=user.get("name", ""),
                license="Pexels License",
                license_url="https://www.pexels.com/license/",
                attribution=f"Video by {user.get('name', 'Pexels contributor')} on Pexels",
            ))
        if assets:
            return assets
        response = self.session.get(
            "https://api.pexels.com/v1/search",
            headers=headers,
            params={"query": query, "per_page": min(limit, 40), "orientation": "landscape"},
            timeout=45,
        )
        response.raise_for_status()
        for photo in response.json().get("photos", []):
            assets.append(MediaAsset(
                source="Pexels",
                title=photo.get("alt") or f"Pexels photo {photo.get('id', '')}",
                url=photo.get("src", {}).get("large2x") or photo.get("src", {}).get("original", ""),
                page_url=photo.get("url", ""),
                mime="image/jpeg",
                media_type="image",
                creator=photo.get("photographer", ""),
                license="Pexels License",
                license_url="https://www.pexels.com/license/",
                attribution=f"Photo by {photo.get('photographer', 'Pexels contributor')} on Pexels",
            ))
        return [item for item in assets if item.url]
