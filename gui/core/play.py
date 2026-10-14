import subprocess
import sys

from core.paths import mpv_path

_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def play(path: str, start: str | None = None):
    """Launch bin/mpv.exe on `path`, optionally seeking to `start` (HH:MM:SS[.ms])."""
    cmd = [mpv_path(), path, "--osd-fractions", "--osd-level=3"]
    if start:
        cmd.append(f"--start={start}")
    subprocess.Popen(
        cmd,
        creationflags=_CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
