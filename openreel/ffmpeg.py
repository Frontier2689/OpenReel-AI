from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def _binary(name: str) -> str:
    bundled = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "bin" / f"{name}.exe"
    if bundled.exists():
        return str(bundled)
    found = shutil.which(name)
    if not found:
        raise FileNotFoundError(f"{name} was not found. Install FFmpeg or use the release build.")
    return found


def normalize(source: Path, destination: Path, duration: int, width: int, height: int, fps: int):
    filter_value = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,fps={fps},format=yuv420p"
    )
    command = [
        _binary("ffmpeg"), "-y", "-stream_loop", "-1", "-i", str(source),
        "-t", str(duration), "-vf", filter_value, "-an", "-c:v", "libx264",
        "-preset", "medium", "-crf", "20", "-movflags", "+faststart", str(destination),
    ]
    subprocess.run(command, check=True, capture_output=True)


def animate_image(
    source: Path, destination: Path, duration: int, width: int, height: int, fps: int,
    direction: int = 1,
):
    frames = duration * fps
    zoom = "min(zoom+0.0008,1.10)" if direction % 2 else "if(eq(on,1),1.10,max(zoom-0.0008,1.0))"
    filter_value = (
        f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
        f"crop={width * 2}:{height * 2},"
        f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={frames}:s={width}x{height}:fps={fps},format=yuv420p"
    )
    command = [
        _binary("ffmpeg"), "-y", "-loop", "1", "-i", str(source), "-t", str(duration),
        "-vf", filter_value, "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-movflags", "+faststart", str(destination),
    ]
    subprocess.run(command, check=True, capture_output=True)


def concatenate(clips: list[Path], destination: Path):
    manifest = destination.parent / "concat.txt"
    manifest.write_text(
        "".join(f"file '{str(path.resolve()).replace(chr(39), chr(39) * 2)}'\n" for path in clips),
        encoding="utf-8",
    )
    command = [
        _binary("ffmpeg"), "-y", "-f", "concat", "-safe", "0", "-i", str(manifest),
        "-c", "copy", "-movflags", "+faststart", str(destination),
    ]
    subprocess.run(command, check=True, capture_output=True)
