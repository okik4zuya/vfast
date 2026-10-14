import json
import os
import subprocess
import sys

from core.paths import ffmpeg_path

_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _yt_dlp_cmd():
    # Explicit interpreter module call so this always runs the venv that's running the
    # GUI, instead of relying on ambient PATH order (see gui-rewrite memory note).
    # Frozen (PyInstaller onefile) builds have no `-m` support since sys.executable is
    # vfast.exe, not python.exe — re-launch the exe itself with the --run-yt-dlp flag that
    # main.py handles instead (see main.py's _run_yt_dlp).
    if getattr(sys, "frozen", False):
        return [sys.executable, "--run-yt-dlp"]
    return [sys.executable, "-m", "yt_dlp"]


def format_selector(height: int | None) -> str:
    if height is None:
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"
    return f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}]"


def fetch_formats(url: str, log=print):
    """Probe a URL with yt-dlp and return (title, [{"label", "height"}, ...]) sorted by height desc."""
    command = _yt_dlp_cmd() + ["-j", "--no-playlist", url]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_CREATE_NO_WINDOW,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        log("[Download] Timed out fetching video info.")
        return "", []

    if result.returncode != 0:
        last_line = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unknown error"
        log(f"[Download] Failed to fetch info: {last_line}")
        return "", []

    try:
        info = json.loads(result.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        log("[Download] Could not parse video info.")
        return "", []

    best_by_height = {}
    for f in info.get("formats", []):
        height = f.get("height")
        if not height or f.get("vcodec", "none") == "none":
            continue
        size = f.get("filesize") or f.get("filesize_approx")
        existing = best_by_height.get(height)
        if existing is None or (size or 0) > (existing or 0):
            best_by_height[height] = size

    options = []
    for height in sorted(best_by_height.keys(), reverse=True):
        size = best_by_height[height]
        size_label = f"~{size / (1024 * 1024):.0f} MB" if size else "size unknown"
        options.append({"label": f"{height}p ({size_label})", "height": height})

    return info.get("title", ""), options


class Downloader:
    """Sequential bulk downloader with a cooperative stop flag + subprocess handle for Stop."""

    def __init__(self):
        self._proc = None
        self._stopped = False

    def stop(self):
        self._stopped = True
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()

    def _download_one(self, project_dir: str, url: str, height: int | None, log) -> bool:
        output_template = os.path.join(project_dir, "%(title)s.%(ext)s")
        command = _yt_dlp_cmd() + [
            "-f", format_selector(height),
            "--merge-output-format", "mp4",
            "--ffmpeg-location", ffmpeg_path(),
            "-o", output_template,
            url,
        ]

        self._proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            creationflags=_CREATE_NO_WINDOW,
        )

        for line in self._proc.stdout:
            log(line.rstrip())

        self._proc.wait()
        returncode = self._proc.returncode
        self._proc = None

        if self._stopped:
            log("[Download] Stopped.")
            return False
        if returncode != 0:
            log(f"[Download] yt-dlp exited with code {returncode}.")
            return False
        return True

    def download_bulk(self, project_dir: str, urls: list[str], height: int | None = None, log=print) -> None:
        self._stopped = False
        total = len(urls)
        succeeded = 0

        for i, url in enumerate(urls, start=1):
            if self._stopped:
                break
            log(f"[Download] ({i}/{total}) Downloading: {url}")
            if self._download_one(project_dir, url, height, log):
                succeeded += 1
                log(f"[Download] ({i}/{total}) Completed.")
            elif self._stopped:
                break

        if self._stopped:
            log(f"[Download] Batch stopped. {succeeded}/{total} completed.")
        else:
            log(f"[Download] Batch finished: {succeeded}/{total} succeeded.")
