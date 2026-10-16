import glob
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Optional

from core.paths import ffprobe_path

VIDEO_EXTS = ("*.mp4", "*.mkv", "*.mov", "*.avi")
AUDIO_EXTS = ("*.mp3", "*.wav", "*.aac", "*.m4a", "*.flac")

_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


@dataclass
class MediaFile:
    path: str
    name: str
    duration: float  # seconds, 0.0 if unknown
    width: int = 0  # 0 if unknown or not a video
    height: int = 0


# (abspath, mtime, size) -> (duration, width, height). Keyed on mtime+size so an edited or replaced
# file is re-probed; failed probes are not cached.
_PROBE_CACHE: dict[tuple[str, float, int], tuple[float, int, int]] = {}
_PROBE_WORKERS = 4


def _probe(path: str) -> tuple[float, int, int]:
    """Duration + first video stream size in ONE ffprobe call (was two); (0.0, 0, 0) if unknown."""
    try:
        st = os.stat(path)
    except OSError:
        return 0.0, 0, 0
    key = (os.path.abspath(path), st.st_mtime, st.st_size)
    hit = _PROBE_CACHE.get(key)
    if hit:
        return hit
    try:
        out = subprocess.check_output(
            [
                ffprobe_path(), "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "format=duration:stream=width,height",
                "-of", "json",
                path,
            ],
            creationflags=_CREATE_NO_WINDOW,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        data = json.loads(out)
        duration = float((data.get("format") or {}).get("duration") or 0.0)
        stream = (data.get("streams") or [{}])[0]
        result = (duration, int(stream.get("width") or 0), int(stream.get("height") or 0))
    except (subprocess.CalledProcessError, ValueError, TypeError, OSError):
        return 0.0, 0, 0
    _PROBE_CACHE[key] = result
    return result


def has_audio_stream(path: str) -> bool:
    try:
        out = subprocess.check_output(
            [
                ffprobe_path(), "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=index",
                "-of", "csv=p=0",
                path,
            ],
            creationflags=_CREATE_NO_WINDOW,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return bool(out)
    except (subprocess.CalledProcessError, OSError):
        return False


def video_fps(path: str) -> str:
    """First video stream frame rate as an ffmpeg rational string ("30000/1001"); "30" if unknown."""
    try:
        out = subprocess.check_output(
            [
                ffprobe_path(), "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=r_frame_rate",
                "-of", "csv=p=0",
                path,
            ],
            creationflags=_CREATE_NO_WINDOW,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        num, _, den = out.partition("/")
        if float(num) > 0 and float(den or 1) > 0:
            return out
    except (subprocess.CalledProcessError, OSError, ValueError):
        pass
    return "30"


def _list(folder: str, patterns, progress: Optional[Callable[[int, int], None]] = None) -> list[MediaFile]:
    paths = [p for pattern in patterns for p in glob.glob(os.path.join(folder, pattern))]
    done = 0
    lock = threading.Lock()

    def probe_one(path: str) -> MediaFile:
        nonlocal done
        duration, width, height = _probe(path)
        if progress:
            with lock:
                done += 1
                progress(done, len(paths))
        return MediaFile(path=os.path.abspath(path), name=os.path.basename(path),
                         duration=duration, width=width, height=height)

    with ThreadPoolExecutor(max_workers=_PROBE_WORKERS) as pool:
        files = list(pool.map(probe_one, paths))
    files.sort(key=lambda m: m.name.lower())
    return files


def list_videos(folder: str, progress: Optional[Callable[[int, int], None]] = None) -> list[MediaFile]:
    return _list(folder, VIDEO_EXTS, progress)


def list_audios(folder: str, progress: Optional[Callable[[int, int], None]] = None) -> list[MediaFile]:
    return _list(folder, AUDIO_EXTS, progress)


def format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "00:00:00.000"
    total_ms = round(seconds * 1000)
    hh, rem = divmod(total_ms, 3_600_000)
    mm, rem = divmod(rem, 60_000)
    ss, ms = divmod(rem, 1000)
    return f"{hh:02d}:{mm:02d}:{ss:02d}.{ms:03d}"
