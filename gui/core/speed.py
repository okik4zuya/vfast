import subprocess
import sys

from core.paths import ffmpeg_path

_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

MIN_SPEED = 0.5
MAX_SPEED = 2.0


def is_valid_speed(multiplier: float) -> bool:
    return MIN_SPEED <= multiplier <= MAX_SPEED


def change_speed(input_path: str, multiplier: float, output_path: str, log=print) -> bool:
    if not is_valid_speed(multiplier):
        log(f"[Speed] Multiplier must be between {MIN_SPEED} and {MAX_SPEED}.")
        return False

    log(f"[Speed] Changing speed to {multiplier}x...")
    proc = subprocess.Popen(
        [
            ffmpeg_path(), "-y", "-i", input_path,
            "-filter_complex",
            f"[0:v]setpts=PTS/{multiplier}[v];[0:a]atempo={multiplier}[a]",
            "-map", "[v]", "-map", "[a]",
            output_path,
        ],
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

    ok = proc.returncode == 0
    log("[Speed] Done." if ok else "[Speed] Failed.")
    return ok
