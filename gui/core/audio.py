import subprocess
import sys

from core.paths import ffmpeg_path, rnnoise_model_path

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


def add_audio(video_path: str, audio_path: str, output_path: str, mix: bool,
              mix_volume: float = 0.3, log=print) -> bool:
    if mix:
        log("[AddAudio] Mixing new track with original audio...")
        cmd = [
            ffmpeg_path(), "-y", "-i", video_path, "-i", audio_path,
            "-filter_complex",
            f"[1:a]volume={mix_volume}[a1];[0:a][a1]amix=inputs=2:duration=shortest[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-shortest",
            output_path,
        ]
    else:
        log("[AddAudio] Replacing original audio...")
        cmd = [
            ffmpeg_path(), "-y", "-i", video_path, "-i", audio_path,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-shortest",
            output_path,
        ]

    ok = _run(cmd, log)
    log("[AddAudio] Done." if ok else "[AddAudio] Failed.")
    return ok


def remove_audio(video_path: str, output_path: str, log=print) -> bool:
    log("[RemoveAudio] Removing audio track...")
    ok = _run(
        [ffmpeg_path(), "-y", "-i", video_path, "-c:v", "copy", "-an", output_path],
        log,
    )
    log("[RemoveAudio] Done." if ok else "[RemoveAudio] Failed.")
    return ok


def denoise_audio(video_path: str, output_path: str, method: str,
                   strength: float, highpass: bool, log=print) -> bool:
    """strength is 1-100; mapped per-filter to its native range."""
    filters = []
    if highpass:
        filters.append("highpass=f=100")
    if method == "anlmdn":
        filters.append(f"anlmdn=s={strength / 1000:.4f}")
    elif method == "arnndn":
        # ffmpeg's filter-option parser treats ':' as a key=value separator, so the
        # Windows drive-letter colon in the model path must be escaped; forward
        # slashes avoid needing to also escape backslashes.
        model = rnnoise_model_path().replace("\\", "/").replace(":", "\\:")
        filters.append(f"arnndn=m='{model}':mix={strength / 100:.3f}")
    else:
        filters.append(f"afftdn=nr={strength:.1f}")

    log(f"[Denoise] Applying {method} (strength={strength})...")
    cmd = [
        ffmpeg_path(), "-y", "-i", video_path,
        "-af", ",".join(filters),
        "-c:v", "copy", "-c:a", "aac",
        output_path,
    ]
    ok = _run(cmd, log)
    log("[Denoise] Done." if ok else "[Denoise] Failed.")
    return ok


def extract_audio(video_path: str, output_path: str, encode_mp3: bool, log=print) -> bool:
    if encode_mp3:
        log("[ExtractAudio] Encoding to MP3...")
        cmd = [ffmpeg_path(), "-y", "-i", video_path, "-vn", "-c:a", "libmp3lame", "-b:a", "192k", output_path]
    else:
        log("[ExtractAudio] Copying original audio stream...")
        cmd = [ffmpeg_path(), "-y", "-i", video_path, "-vn", "-c:a", "copy", output_path]

    ok = _run(cmd, log)
    log("[ExtractAudio] Done." if ok else "[ExtractAudio] Failed.")
    return ok
