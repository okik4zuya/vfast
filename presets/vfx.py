"""Command-line front end for the Effects engine (gui/core/effects.py + gui/core/render.py).

    vfx.py --list
    vfx.py cinematic video.mp4
    vfx.py youtube-vlog,caption video.mp4 out.mp4 --text "Halo" --duration 5
    vfx.py watermark video.mp4 --logo logo.png
    vfx.py shorts video.mp4 --speed 1.1 --overlay        # also apply video.overlay.json

Same code path as the Effects panel: everything runs as ONE ffmpeg pass.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "gui"))

from core import effects, render, spec  # noqa: E402


def show_list():
    print("\nPRESET (gabungkan dengan koma, mis. cinematic,fade,loudnorm):")
    for name, p in effects.PRESETS.items():
        print(f"  {name:<10} {p.desc}")
    print("\nPAKET:")
    for name, members in effects.PACKS.items():
        print(f"  {name:<18} = {','.join(members)}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("preset", nargs="?", help="preset/paket, dipisah koma")
    ap.add_argument("input", nargs="?")
    ap.add_argument("output", nargs="?")
    # -Text style aliases keep the old PowerShell invocation working
    ap.add_argument("--text", "-Text", default="", help="teks untuk preset caption")
    ap.add_argument("--duration", "-Duration", type=float, default=0, help="caption: lama tampil (detik), 0 = sepanjang video")
    ap.add_argument("--logo", "-Logo", default="", help="gambar untuk preset watermark")
    ap.add_argument("--speed", "-Speed", type=float, default=1.0)
    ap.add_argument("--quality", "-Quality", choices=sorted(render.SPEED_TIERS), default="balanced")
    ap.add_argument("--overlay", "-Overlay", action="store_true", help="sertakan efek <video>.overlay.json")
    ap.add_argument("--list", "-List", action="store_true")
    a = ap.parse_args()

    if a.list or not a.preset:
        show_list()
        return 0
    if not a.input or not os.path.isfile(a.input):
        print(f"File input tidak ditemukan: {a.input}", file=sys.stderr)
        return 2

    names, warnings = effects.normalize([n.strip().lower() for n in a.preset.split(",") if n.strip()])
    for w in warnings:
        print("peringatan:", w)
    out = a.output
    if not out:
        base = os.path.splitext(a.input)[0]
        out = f"{base}_{'+'.join(a.preset.split(','))}.mp4"

    ok = render.render(
        a.input, out, presets=names,
        params={"caption": {"text": a.text, "duration": a.duration}, "watermark": {"path": a.logo}},
        overlay_effects=spec.usable_overlay(spec.load_overlay(a.input)) if a.overlay else [],
        speed=a.speed, quality=a.quality, log=print)
    if ok:
        print(f"\nSelesai: {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
