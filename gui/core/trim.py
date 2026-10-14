import os
import subprocess
import sys

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


def trim_video(input_path: str, start: str, end: str, output_path: str, log=print,
                preset: str = "fast", crf: int = 18) -> bool:
    log(f"[Trim] Trimming {start} - {end}...")
    ok = _run(
        [
            ffmpeg_path(), "-y", "-ss", start, "-to", end, "-i", input_path,
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ],
        log,
    )
    log("[Trim] Done." if ok else "[Trim] Failed.")
    return ok


def trim_audio(input_path: str, start: str, end: str, output_path: str, encode_mp3: bool, log=print) -> bool:
    log(f"[Trim] Trimming {start} - {end}...")
    codec_args = ["-c:a", "libmp3lame", "-b:a", "192k"] if encode_mp3 else ["-c:a", "aac", "-b:a", "192k"]
    ok = _run(
        [
            ffmpeg_path(), "-y", "-ss", start, "-to", end, "-i", input_path,
            "-vn", *codec_args,
            output_path,
        ],
        log,
    )
    log("[Trim] Done." if ok else "[Trim] Failed.")
    return ok


def bulk_trim(input_path: str, segments: list[tuple[str, str]], output_dir: str,
              is_video: bool, encode_mp3: bool = False, log=print,
              preset: str = "fast", crf: int = 18) -> int:
    """Runs one trim per (start, end) segment. Returns clip count created."""
    ext = ".mp4" if is_video else (".mp3" if encode_mp3 else ".m4a")
    count = 0
    for i, (start, end) in enumerate(segments, start=1):
        if not start or not end:
            continue
        output_path = os.path.join(output_dir, f"clip_{i}{ext}")
        if is_video:
            ok = trim_video(input_path, start, end, output_path, log=log, preset=preset, crf=crf)
        else:
            ok = trim_audio(input_path, start, end, output_path, encode_mp3, log=log)
        if ok:
            count += 1
    log(f"[Trim] Done! Created {count} clips.")
    return count
