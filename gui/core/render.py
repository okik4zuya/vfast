"""The single encode point for the Effects panel.

Overlay effects + preset effects + speed + audio filters are stitched into ONE filtergraph and rendered
with ONE ffmpeg process. Order of the video graph:

    overlay effects (input pixels, input timeline)
      -> layout / look / zoom / caption / watermark   (core.effects.build_chain)
      -> setpts (speed) -> fade                        (fade is timed on the sped-up timeline)

Audio: overlay mute -> cleanup (voice) -> atempo -> loudnorm -> afade.
"""
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass

from core import effects
from core.effects import FADE_SECONDS, LOGO_OPACITY, LOUDNORM
from core.media import _probe, has_audio_stream, video_fps
from core.overlay import build_filter
from core.paths import ffmpeg_path
from core.speed import MAX_SPEED, MIN_SPEED, is_valid_speed

_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# name -> (x264 preset, crf); same tiers as the Trim/Cut/Overlay panels.
SPEED_TIERS = {"fast": ("veryfast", 23), "balanced": ("fast", 18), "high": ("slow", 16)}


@dataclass
class MediaInfo:
    duration: float
    width: int
    height: int
    fps: str
    has_audio: bool


def probe_info(path: str) -> MediaInfo:
    duration, width, height = _probe(path)
    return MediaInfo(duration, width, height, video_fps(path), has_audio_stream(path))


def run_ffmpeg(cmd: list[str], log) -> bool:
    with subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        encoding="utf-8", errors="replace", creationflags=_CREATE_NO_WINDOW,
    ) as proc:
        for line in proc.stdout:
            log(line.rstrip())
    return proc.returncode == 0


def _g(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".")


def build_command(info: MediaInfo, input_path: str, output_path: str, *, presets, params=None,
                  overlay_effects=(), speed: float = 1.0, window: tuple[float, float] | None = None,
                  preset: str = "fast", crf: int = 18, tmpdir: str, ffmpeg: str | None = None) -> list[str]:
    """Pure (apart from writing text files into tmpdir): everything needed for the single ffmpeg call.

    Raises ValueError/KeyError on a bad spec.
    """
    if not is_valid_speed(speed):
        raise ValueError(f"speed harus antara {MIN_SPEED} dan {MAX_SPEED}")
    if os.path.abspath(input_path) == os.path.abspath(output_path):
        raise ValueError("output tidak boleh sama dengan input")

    names, _ = effects.normalize(presets)
    offset = window[0] if window else 0.0
    in_dur = (window[1] - window[0]) if window else info.duration
    chain = effects.build_chain(names, params, width=info.width, height=info.height,
                                fps=info.fps, tmpdir=tmpdir)

    use_audio = info.has_audio and not chain.mute  # a dangling [outa] label would make ffmpeg fail
    fc, images, _vlab, alab = build_filter(
        list(overlay_effects), use_audio, offset=offset, tmpdir=tmpdir,
        duration=(window[1] if window else 1e9))
    parts = [fc]
    cur = "[outv]"

    if chain.vf:
        parts.append(f"{cur}{chain.vf}[ev]")
        cur = "[ev]"
    inputs = list(images)
    if chain.logo:
        idx = 1 + len(images)
        inputs.append(chain.logo)
        parts.append(f"[{idx}:v]scale={chain.logo_w}:-1,format=rgba,colorchannelmixer=aa={LOGO_OPACITY}[lg];"
                     f"{cur}[lg]overlay=W-w-24:24[ew]")
        cur = "[ew]"

    final_dur = in_dur / speed if in_dur > 0 else 0.0
    fade_d = min(FADE_SECONDS, final_dur / 2) if final_dur > 0 else 0.0
    post = []
    if speed != 1.0:
        post.append(f"setpts=PTS/{_g(speed)}")
    if chain.fade and fade_d > 0:
        post += [f"fade=t=in:st=0:d={_g(fade_d)}", f"fade=t=out:st={_g(final_dur - fade_d)}:d={_g(fade_d)}"]
    if post:
        parts.append(f"{cur}{','.join(post)}[vout]")
        cur = "[vout]"

    amap, reencode_audio = None, False
    if use_audio:
        stages = list(chain.af)
        if speed != 1.0:
            stages.append(f"atempo={_g(speed)}")
        if chain.norm:
            stages.append(LOUDNORM)
        if chain.fade and fade_d > 0:
            stages += [f"afade=t=in:st=0:d={_g(fade_d)}", f"afade=t=out:st={_g(final_dur - fade_d)}:d={_g(fade_d)}"]
        if stages:
            parts.append(f"{'[0:a]' if alab == '0:a' else alab}{','.join(stages)}[aout]")
            amap, reencode_audio = "[aout]", True
        else:
            amap, reencode_audio = alab, alab != "0:a"

    cmd = [ffmpeg or ffmpeg_path(), "-y"]
    if window:
        cmd += ["-ss", str(window[0]), "-t", str(window[1] - window[0])]
    cmd += ["-i", input_path]
    for extra in inputs:
        cmd += ["-i", extra]
    cmd += ["-filter_complex", ";".join(parts), "-map", cur]
    if amap:
        cmd += ["-map", amap]
    cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]
    if output_path.lower().endswith((".mp4", ".mov", ".m4v")):
        cmd += ["-movflags", "+faststart"]  # an mp4-muxer option; other containers would reject it
    if not amap:
        cmd += ["-an"]
    elif reencode_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-c:a", "copy"]
    cmd.append(output_path)
    return cmd


def render(input_path: str, output_path: str, *, presets, params=None, overlay_effects=(),
           speed: float = 1.0, window: tuple[float, float] | None = None,
           quality: str = "balanced", log=print) -> bool:
    """One ffmpeg process for effects + overlay + speed + audio. window=(start, end) renders a test slice."""
    x264_preset, crf = SPEED_TIERS.get(quality, SPEED_TIERS["balanced"])
    info = probe_info(input_path)
    with tempfile.TemporaryDirectory() as tmp:
        try:
            cmd = build_command(info, input_path, output_path, presets=presets, params=params,
                                overlay_effects=overlay_effects, speed=speed, window=window,
                                preset=x264_preset, crf=crf, tmpdir=tmp)
        except (ValueError, KeyError) as exc:
            log(f"[Effects] Bad spec: {exc}")
            return False
        log("[Effects] Rendering (1 pass)...")
        ok = run_ffmpeg(cmd, log)
    log("[Effects] Done." if ok else "[Effects] Failed.")
    return ok
