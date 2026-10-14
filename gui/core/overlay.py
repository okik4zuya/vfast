import os
import subprocess
import sys
import tempfile

from core.paths import ffmpeg_path
from core.media import has_audio_stream
from core.cut import parse_time

_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

DEFAULT_FONT = "C:/Windows/Fonts/arial.ttf"

# Effect spec (one dict per effect). Times are seconds or HH:MM:SS[.mmm], relative to the input
# video (so run this on the already-cut video). "start"/"end" omitted = whole video.
#   box      x y w h [color=black]
#   blur     x y w h [strength=20]
#   pixelate x y w h [block=16]
#   text     text x y [size=36] [color=white] [bg=None] [font=DEFAULT_FONT]
#   image    path x y [w] [h]
#   mute     (audio silenced between start and end)
EFFECT_TYPES = ("box", "blur", "pixelate", "text", "image", "mute")


def _esc_path(p: str) -> str:
    """Path -> ffmpeg filter-option value (forward slashes, escaped drive colon, quoted)."""
    return "'" + p.replace("\\", "/").replace(":", "\\:") + "'"


def _t(value, default: float) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return parse_time(str(value))


def _enable(start: float, end: float) -> str:
    return f"enable='between(t,{start:.3f},{end:.3f})'"


def build_filter(effects: list[dict], has_audio: bool, offset: float = 0.0,
                 first_image_input: int = 1, tmpdir: str = "", duration: float = 1e9):
    """Returns (filter_complex, image_paths, out_v_label, out_a_label_or_None).

    offset shifts effect times back (used when only a window of the input is processed).
    """
    parts = []
    images = []
    cur = "0:v"
    audio_filters = []
    n = 0

    for i, fx in enumerate(effects):
        kind = fx.get("type")
        if kind not in EFFECT_TYPES:
            raise ValueError(f"unknown effect type: {kind!r}")
        s = _t(fx.get("start"), 0.0) - offset
        e = _t(fx.get("end"), duration) - offset
        if e <= 0:
            continue  # entirely before the window
        s = max(s, 0.0)
        en = _enable(s, e)

        if kind == "mute":
            audio_filters.append(f"volume=0:{en}")
            continue

        nxt = f"v{n + 1}"
        n += 1
        x, y = int(fx.get("x", 0)), int(fx.get("y", 0))

        if kind == "box":
            w, h = int(fx["w"]), int(fx["h"])
            color = fx.get("color", "black")
            parts.append(f"[{cur}]drawbox=x={x}:y={y}:w={w}:h={h}:color={color}:t=fill:{en}[{nxt}]")

        elif kind in ("blur", "pixelate"):
            w, h = int(fx["w"]), int(fx["h"])
            if kind == "blur":
                r = max(1, min(int(fx.get("strength", 20)), min(w, h) // 2 - 1))
                cr = max(0, min(r, min(w, h) // 4 - 1))  # chroma plane is half-size
                proc = f"boxblur=luma_radius={r}:luma_power=3:chroma_radius={cr}:chroma_power=3"
            else:
                b = max(2, int(fx.get("block", 16)))
                proc = (f"scale=max(1\\,{w}/{b}):max(1\\,{h}/{b}),"
                        f"scale={w}:{h}:flags=neighbor")
            parts.append(
                f"[{cur}]split[m{i}a][m{i}b];"
                f"[m{i}b]crop={w}:{h}:{x}:{y},{proc}[m{i}c];"
                f"[m{i}a][m{i}c]overlay={x}:{y}:{en}[{nxt}]"
            )

        elif kind == "text":
            tf = os.path.join(tmpdir, f"text{i}.txt")
            with open(tf, "w", encoding="utf-8", newline="") as f:
                f.write(fx["text"])
            font = fx.get("font", DEFAULT_FONT)
            opts = (f"fontfile={_esc_path(font)}:textfile={_esc_path(tf)}:x={x}:y={y}:"
                    f"fontsize={int(fx.get('size', 36))}:fontcolor={fx.get('color', 'white')}")
            if fx.get("bg"):
                opts += f":box=1:boxcolor={fx['bg']}:boxborderw=10"
            parts.append(f"[{cur}]drawtext={opts}:{en}[{nxt}]")

        elif kind == "image":
            idx = first_image_input + len(images)
            images.append(fx["path"])
            scale = ""
            if fx.get("w") or fx.get("h"):
                scale = f"scale={int(fx.get('w', -1))}:{int(fx.get('h', -1))},"
            parts.append(f"[{idx}:v]{scale}format=rgba[img{i}];"
                         f"[{cur}][img{i}]overlay={x}:{y}:{en}[{nxt}]")

        cur = nxt

    out_a = None
    if has_audio and audio_filters:
        parts.append("[0:a]" + ",".join(audio_filters) + "[outa]")
        out_a = "[outa]"
    elif has_audio:
        out_a = "0:a"

    if cur == "0:v":
        parts.append("[0:v]null[outv]")
    else:
        parts.append(f"[{cur}]null[outv]")
    return ";".join(parts), images, "[outv]", out_a


def _run(cmd: list[str], log) -> bool:
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        encoding="utf-8", errors="replace", creationflags=_CREATE_NO_WINDOW,
    )
    for line in proc.stdout:
        log(line.rstrip())
    proc.wait()
    return proc.returncode == 0


def overlay_media(input_path: str, effects: list[dict], output_path: str, log=print,
                  preset: str = "fast", crf: int = 18,
                  window: tuple[float, float] | None = None) -> bool:
    """Render effects onto a video. window=(start, end) renders only that slice (for test clips)."""
    has_audio = has_audio_stream(input_path)
    offset = window[0] if window else 0.0
    with tempfile.TemporaryDirectory() as tmp:
        try:
            fc, images, vlab, alab = build_filter(
                effects, has_audio, offset=offset, tmpdir=tmp,
                duration=(window[1] if window else 1e9))
        except (ValueError, KeyError) as exc:
            log(f"[Overlay] Bad effect spec: {exc}")
            return False

        cmd = [ffmpeg_path(), "-y"]
        if window:
            cmd += ["-ss", str(window[0]), "-t", str(window[1] - window[0])]
        cmd += ["-i", input_path]
        for img in images:
            cmd += ["-i", img]
        cmd += ["-filter_complex", fc, "-map", vlab]
        if alab:
            cmd += ["-map", alab]
        cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]
        if alab == "0:a":
            cmd += ["-c:a", "copy"]
        elif alab:
            cmd += ["-c:a", "aac", "-b:a", "192k"]
        cmd.append(output_path)

        log("[Overlay] Rendering...")
        ok = _run(cmd, log)
    log("[Overlay] Done." if ok else "[Overlay] Failed.")
    return ok


def preview_frame(input_path: str, t: float, output_png: str, effects: list[dict] | None = None,
                  grid: bool = False, log=print) -> bool:
    """One PNG at time t with the effects active at t applied; grid=True adds a 100px coordinate grid."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            fc, images, vlab, _ = build_filter(
                effects or [], False, offset=t, tmpdir=tmp, duration=t + 1)
        except (ValueError, KeyError) as exc:
            log(f"[Overlay] Bad effect spec: {exc}")
            return False
        if grid:
            labels = []
            for gx in range(0, 3840, 100):
                labels.append(f"drawtext=fontfile={_esc_path(DEFAULT_FONT)}:text='{gx}':x={gx + 2}:y=2:"
                              f"fontsize=14:fontcolor=yellow:box=1:boxcolor=black@0.6")
            for gy in range(100, 2160, 100):
                labels.append(f"drawtext=fontfile={_esc_path(DEFAULT_FONT)}:text='{gy}':x=2:y={gy + 2}:"
                              f"fontsize=14:fontcolor=yellow:box=1:boxcolor=black@0.6")
            fc += f";{vlab}drawgrid=w=100:h=100:t=1:c=red@0.5," + ",".join(labels) + "[g]"
            vlab = "[g]"
        cmd = [ffmpeg_path(), "-y", "-ss", str(t), "-i", input_path]
        for img in images:
            cmd += ["-i", img]
        cmd += ["-filter_complex", fc, "-map", vlab, "-frames:v", "1", "-update", "1", output_png]
        return _run(cmd, log)
