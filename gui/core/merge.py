import os
import subprocess
import sys
import tempfile

from core.paths import ffmpeg_path

_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _run(cmd, log):
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
        creationflags=_CREATE_NO_WINDOW,
    )
    for line in proc.stdout:
        log(line.rstrip())
    proc.wait()
    return proc.returncode == 0


def merge_videos(paths: list[str], output_path: str, log=print) -> bool:
    if not paths:
        log("[Merge] No files selected.")
        return False

    fd, filelist_path = tempfile.mkstemp(suffix=".txt", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for p in paths:
                escaped = p.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

        log("[Merge] Merging videos...")
        ok = _run(
            [
                ffmpeg_path(), "-y", "-f", "concat", "-safe", "0",
                "-i", filelist_path,
                "-c:v", "libx264", "-c:a", "aac",
                output_path,
            ],
            log,
        )
    finally:
        os.remove(filelist_path)

    log("[Merge] Done." if ok else "[Merge] Failed.")
    return ok


def merge_audios(paths: list[str], output_path: str, log=print) -> bool:
    if not paths:
        log("[Merge] No files selected.")
        return False

    fd, filelist_path = tempfile.mkstemp(suffix=".txt", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for p in paths:
                escaped = p.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

        log("[Merge] Merging audios...")
        ok = _run(
            [
                ffmpeg_path(), "-y", "-f", "concat", "-safe", "0",
                "-i", filelist_path,
                "-c:a", "libmp3lame", "-b:a", "192k",
                output_path,
            ],
            log,
        )
    finally:
        os.remove(filelist_path)

    log("[Merge] Done." if ok else "[Merge] Failed.")
    return ok
