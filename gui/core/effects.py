"""Effect presets and packs, as pure data + a chain builder (no subprocess, no tkinter).

A *preset* is one named look/fix ("punchy", "vertical", "loudnorm"...). A *pack* is a ready list of
presets ("youtube-vlog"). `build_chain` turns a preset list into the pieces `core.render` stitches into
ONE ffmpeg filtergraph, so any mix of effects + overlay + speed costs a single encode.

Canonical order (the order the user ticks presets in never matters):
    layout (vertical/square/hd) -> look -> zoom -> caption -> watermark -> [speed] -> fade
Overlay effects (box/blur/text...) are applied BEFORE all of this, on the untouched input frame, because
their coordinates are pixels of the input video (see core/overlay.py).
"""
import os
from dataclasses import dataclass, field

from core.overlay import DEFAULT_FONT, _esc_path

LAYOUT, LOOK, ZOOM, CAPTION, WATERMARK, FADE, AUDIO = "layout", "look", "zoom", "caption", "watermark", "fade", "audio"
_ORDER = (LAYOUT, LOOK, ZOOM, CAPTION, WATERMARK, FADE, AUDIO)

LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"
FADE_SECONDS = 0.5
LOGO_WIDTH_FRACTION = 0.15
LOGO_OPACITY = 0.8


@dataclass(frozen=True)
class Preset:
    desc: str
    stage: str
    vf: str = ""          # plain video filter(s), comma separated
    af: str = ""          # audio cleanup filter(s) applied before tempo/loudnorm
    norm: bool = False    # needs loudnorm (deduplicated across presets)
    params: tuple = ()    # names of user parameters ("caption" text, "watermark" path)


PRESETS: dict[str, Preset] = {
    # --- color / look ---
    "punchy":    Preset("Warna lebih hidup (kontras + saturasi naik sedikit)", LOOK,
                        vf="eq=contrast=1.08:saturation=1.2:gamma=1.02"),
    "bright":    Preset("Cerahkan video gelap", LOOK,
                        vf="eq=brightness=0.06:contrast=1.05:gamma=1.1"),
    "cinematic": Preset("Look sinematik ringan: teal-orange halus + vignette", LOOK,
                        vf="eq=contrast=1.1:saturation=1.1,colorbalance=rs=-0.04:bs=0.05:rh=0.05:bh=-0.04,vignette=PI/6"),
    "warm":      Preset("Nuansa hangat (golden hour)", LOOK, vf="colortemperature=temperature=5200"),
    "cool":      Preset("Nuansa dingin / biru", LOOK, vf="colortemperature=temperature=8500"),
    "vintage":   Preset("Retro: warna pudar + grain + vignette", LOOK,
                        vf="curves=preset=vintage,noise=alls=10:allf=t,vignette=PI/5"),
    "bw":        Preset("Hitam putih dengan kontras", LOOK, vf="hue=s=0,eq=contrast=1.15"),
    # --- quality ---
    "sharpen":   Preset("Pertajam ringan", LOOK, vf="unsharp=5:5:0.8:5:5:0.0"),
    "clean":     Preset("Kurangi noise video + pertajam sedikit", LOOK,
                        vf="hqdn3d=2:1:3:3,unsharp=5:5:0.6:5:5:0.0"),
    "grain":     Preset("Film grain tipis", LOOK, vf="noise=alls=8:allf=t"),
    "vignette":  Preset("Sudut gelap halus", LOOK, vf="vignette=PI/5"),
    # --- motion ---
    "fade":      Preset("Fade in & fade out 0,5 detik (video + audio)", FADE),
    "zoomin":    Preset("Zoom masuk pelan (Ken Burns, hingga 1.15x)", ZOOM),
    # --- format ---
    "vertical":  Preset("9:16 (Shorts/Reels/TikTok): video di tengah, latar blur", LAYOUT),
    "square":    Preset("1:1 (Instagram): video di tengah, latar blur", LAYOUT),
    "hd":        Preset("Skala ke 1080p (tinggi 1080, lebar menyesuaikan)", LAYOUT),
    # --- overlay-ish (take a parameter) ---
    "caption":   Preset("Teks bawah dengan kotak latar", CAPTION, params=("caption",)),
    "watermark": Preset("Logo kanan atas, 15% lebar video, transparan 80%", WATERMARK, params=("watermark",)),
    # --- audio ---
    "loudnorm":  Preset("Samakan volume audio (-16 LUFS)", AUDIO, norm=True),
    "voice":     Preset("Rapikan suara bicara: buang dengung + kurangi noise + normalisasi", AUDIO,
                        af="highpass=f=80,lowpass=f=12000,afftdn=nf=-25", norm=True),
    "mute":      Preset("Hapus audio", AUDIO),
}

# Packs are flat lists of presets (a pack never contains another pack).
PACKS: dict[str, list[str]] = {
    # YouTube
    "youtube":           ["punchy", "clean", "loudnorm"],
    "youtube-vlog":      ["punchy", "clean", "sharpen", "voice", "fade"],
    "youtube-tutorial":  ["clean", "sharpen", "voice", "hd"],
    "youtube-cinematic": ["cinematic", "sharpen", "grain", "loudnorm", "fade"],
    "youtube-gaming":    ["punchy", "sharpen", "loudnorm"],
    "youtube-podcast":   ["bright", "clean", "voice"],
    "youtube-review":    ["bright", "punchy", "clean", "sharpen", "voice"],
    "youtube-outdoor":   ["punchy", "warm", "sharpen", "loudnorm"],
    # short-form vertical
    "shorts":            ["vertical", "punchy", "loudnorm", "fade"],
    "tiktok":            ["vertical", "punchy", "sharpen", "loudnorm"],
    "reels":             ["vertical", "punchy", "warm", "loudnorm"],
    "shorts-clean":      ["vertical", "clean", "sharpen", "voice"],
    "shorts-cinematic":  ["vertical", "cinematic", "grain", "loudnorm", "fade"],
    # Instagram / WhatsApp
    "instagram-feed":    ["square", "punchy", "sharpen", "loudnorm"],
    "whatsapp":          ["hd", "clean", "loudnorm"],
    # looks
    "vlog":              ["punchy", "clean", "sharpen", "voice"],
    "film":              ["cinematic", "grain", "fade"],
    "retro":             ["vintage", "warm", "vignette", "fade"],
    "bw-drama":          ["bw", "vignette", "grain", "fade"],
    "moody":             ["cinematic", "cool", "vignette"],
    "golden":            ["warm", "punchy", "vignette"],
    # quick fixes
    "fix-dark":          ["bright", "clean", "loudnorm"],
    "fix-noisy":         ["clean", "voice"],
    "fix-audio":         ["voice"],
    "fix-sharp":         ["clean", "sharpen", "hd"],
}


def expand(names) -> list[str]:
    """Pack names -> their presets; plain preset names pass through. Unknown names are kept as-is."""
    out: list[str] = []
    for n in names:
        out.extend(PACKS.get(n, [n]))
    return out


def normalize(names) -> tuple[list[str], list[str]]:
    """Expand packs, drop unknown names, de-duplicate, keep one layout preset.

    Returns (clean preset names in the order given, warnings). Never raises: this is what runs on a
    spec loaded from disk, which may be stale or hand-edited.
    """
    warnings: list[str] = []
    seen: list[str] = []
    layout: str | None = None
    for n in expand(names):
        if n not in PRESETS:
            warnings.append(f"preset tidak dikenal dibuang: {n!r}")
            continue
        if n in seen:
            continue
        if PRESETS[n].stage == LAYOUT:
            if layout:
                warnings.append(f"{n!r} dibuang: hanya satu format ({layout!r}) yang bisa aktif")
                continue
            layout = n
        seen.append(n)
    return seen, warnings


@dataclass
class Chain:
    vf: str = ""                      # filters to follow an input label, "" if none
    logo: str | None = None           # watermark image path (needs an extra ffmpeg input)
    logo_w: int = 0                   # watermark width in px for the final frame
    fade: bool = False
    af: list[str] = field(default_factory=list)   # audio cleanup, before tempo
    norm: bool = False
    mute: bool = False
    size: tuple[int, int] = (0, 0)    # frame size after the video chain


def preview_filters(chain: "Chain") -> tuple[str, str]:
    """(video graph, audio graph) for mpv's lavfi bridge; "" where nothing applies.

    Live preview covers layout/look/zoom/caption and the audio filters. Overlay effects, watermark,
    speed and fade are left to the exact 10 s test render (they need extra inputs or the output timeline)."""
    af = ["volume=0"] if chain.mute else list(chain.af) + ([LOUDNORM] if chain.norm else [])
    return chain.vf, ",".join(af)


def _even(v: float) -> int:
    return max(2, int(round(v / 2.0)) * 2)


def _layout_filter(name: str) -> tuple[str, tuple[int, int] | None]:
    if name in ("vertical", "square"):
        w, h = (1080, 1920) if name == "vertical" else (1080, 1080)
        # Blurred background is built at 1/4 size then scaled up: same look, far cheaper than blurring 1080p.
        bw, bh = w // 4, h // 4
        return (
            "split[fxa][fxb];"
            f"[fxa]scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},boxblur=8:2,"
            f"scale={w}:{h}[fxbg];"
            f"[fxb]scale={w}:{h}:force_original_aspect_ratio=decrease[fxfg];"
            "[fxbg][fxfg]overlay=(W-w)/2:(H-h)/2,setsar=1"
        ), (w, h)
    return "scale=-2:1080:flags=lanczos", None  # hd: width depends on the input


def build_chain(names, params: dict | None = None, *, width: int, height: int, fps: str = "30",
                tmpdir: str = "") -> Chain:
    """Preset names (already normalized) -> Chain. Raises ValueError on missing parameters."""
    params = params or {}
    presets = [n for n in names if n in PRESETS]
    names_in_order = list(PRESETS)
    ordered = sorted(presets, key=lambda n: (_ORDER.index(PRESETS[n].stage), names_in_order.index(n)))
    chain = Chain(size=(width, height))
    pieces: list[str] = []
    w, h = width, height

    for n in ordered:
        p = PRESETS[n]
        if p.stage == LAYOUT:
            f, size = _layout_filter(n)
            pieces.append(f)
            w, h = size if size else (_even(w * 1080 / h) if h else w, 1080)
        elif p.stage == LOOK:
            pieces.append(p.vf)
        elif p.stage == ZOOM:
            if not (w and h):
                raise ValueError("zoomin butuh ukuran video yang terbaca")
            pieces.append("zoompan=z='min(zoom+0.0006,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                          f"d=1:s={w}x{h}:fps={fps}")
        elif p.stage == CAPTION:
            cap = params.get("caption") or {}
            text = (cap.get("text") or "").strip()
            if not text:
                raise ValueError("caption butuh teks")
            if not tmpdir:
                raise ValueError("caption butuh folder sementara")
            tf = os.path.join(tmpdir, "caption.txt")
            with open(tf, "w", encoding="utf-8", newline="") as f:
                f.write(text)
            dur = float(cap.get("duration") or 0)
            en = f":enable='between(t,0,{dur:.3f})'" if dur > 0 else ""
            pieces.append(
                f"drawtext=fontfile={_esc_path(DEFAULT_FONT)}:textfile={_esc_path(tf)}:fontsize=h/18:"
                "fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=14:"
                f"x=(w-text_w)/2:y=h-text_h-h/12{en}")
        elif p.stage == WATERMARK:
            path = (params.get("watermark") or {}).get("path") or ""
            if not path:
                raise ValueError("watermark butuh gambar logo")
            chain.logo = path
            chain.logo_w = _even((w or 1920) * LOGO_WIDTH_FRACTION)
        elif p.stage == FADE:
            chain.fade = True
        elif p.stage == AUDIO:
            if n == "mute":
                chain.mute = True
            if p.af:
                chain.af.append(p.af)
            chain.norm = chain.norm or p.norm

    chain.vf = ",".join(x for x in pieces if x)
    chain.size = (w, h)
    return chain
