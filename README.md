# OpenReel AI

OpenReel AI is a Windows desktop application that turns a text prompt into an
MP4. Its default renderer searches open public-media repositories, prefers
matching motion clips, animates still images when needed, records attribution,
and joins the results into one video up to 120 seconds long. Neural providers
remain available as an optional rendering mode.

## What this build supports

- 15–120 second projects, rendered as 5-second shots
- No-key Wikimedia Commons retrieval and composition mode
- Source, creator, license, and attribution manifest for retrieved assets
- Temporary source downloads removed after successful encoding
- Optional Replicate and Hugging Face inference endpoints
- Any OpenAI-compatible text model for scene planning
- A deterministic built-in planner when no text-model key is configured
- Configurable model IDs: the application is not locked to a vendor or model
- H.264 `.mp4` output
- Cancellation, progress reporting, resumable project folders, and logs
- A GitHub Actions workflow that produces a portable Windows ZIP and EXE

Model weights are intentionally not embedded in the EXE. Modern video model
weights are often tens of gigabytes, and ordinary Windows PCs cannot execute
them efficiently. The application is self-contained; generation is performed
by the provider selected in Settings (or by a compatible endpoint you host).

## Build on GitHub

1. Create a repository and copy this project into it.
2. Push to `main`.
3. Open **Actions → Build Windows executable → Run workflow**.
4. Download the `OpenReel-AI-Windows` artifact.

Extract the source ZIP before uploading it. GitHub must preserve the
`openreel/`, `tests/`, and `.github/workflows/` directories; uploading the
files from inside those directories into the repository root will break Python
imports and the build workflow.

Creating a tag such as `v0.1.0` also creates a GitHub Release containing the
portable ZIP.

## Run from source

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m openreel
```

FFmpeg must be on PATH when running from source. Release builds download and
bundle `ffmpeg.exe` and `ffprobe.exe` automatically.

## Provider setup

Open **Settings** inside the app.

- **Public assets:** selected by default and requires no account or API key.
  OpenReel searches Wikimedia Commons and writes `sources.json` beside the
  finished video. This mode retrieves and edits existing media; it does not
  synthesize novel photorealistic motion.
- **Pexels:** an optional free API key materially improves stock-video search.
  When configured, OpenReel searches Pexels first and uses Wikimedia Commons
  as the no-key fallback. Retrieved items retain their source and license data.

- **Replicate:** paste an API token and a public model slug such as
  `owner/model`. OpenReel calls the model prediction API and polls until the
  clip is ready.
- **Hugging Face:** paste a token and a model ID. The selected inference
  endpoint must return video bytes or a downloadable video URL.
- **Text planner:** optionally configure any OpenAI-compatible `/chat/completions`
  endpoint. Without it, OpenReel uses its local planner.

Provider terms, model licenses, rate limits, and content policies still apply.
Only use source material and likenesses you have the right to use.

## Development

```powershell
pip install -r requirements-dev.txt
pytest
ruff check .
```

## Architecture

`openreel/planner.py` creates a project/scene manifest. `providers.py` turns
each scene prompt into a clip. `pipeline.py` owns retries, downloads, resume,
normalization, and concatenation. `ffmpeg.py` produces the final MP4.

## License

MIT. Dependencies and remotely selected models retain their own licenses.
