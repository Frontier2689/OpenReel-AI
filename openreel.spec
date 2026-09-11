# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH)
bin_dir = root / "bin"
binaries = []
for name in ("ffmpeg.exe", "ffprobe.exe"):
    path = bin_dir / name
    if path.exists():
        binaries.append((str(path), "bin"))

a = Analysis(
    ["openreel/__main__.py"],
    pathex=[str(root)],
    binaries=binaries,
    hiddenimports=["keyring.backends.Windows"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="OpenReelAI", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, console=False,
)
