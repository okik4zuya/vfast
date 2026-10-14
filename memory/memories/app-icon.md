---
name: app-icon
description: vfast main app icon — locked SVG design, rationale, and the Pillow-based generator that produces all PNG/ICO sizes
metadata:
  type: project
  tier: T1
  created: 2026-09-12 10:28
  updated: 2026-10-14 18:14
---

# vfast — App Icon

**Status: locked.** Design source is [assets/icon/app-icon.svg](../../assets/icon/app-icon.svg).

## Design

Skewed rounded-square blue box with a white play triangle sharing the skew, plus a fan of rounded
solid speed bars (with a soft blurred glow pass behind them) trailing from the lower-left. Iterated
through several rounds with the user:

- Rotation → **skew** (`skewX(-18deg)`, italic-style lean, not a rotation) — user explicitly wanted
  skew, not tilt.
- Tried thin fading-gradient speed lines, then a stroboscopic afterimage/echo trail (rejected —
  removed), then settled on **rounded solid bars** (`stroke-linecap="round"`, flat white, no
  gradient fade) — sharp-pointed wedges and soft/glowing gradients were both explicitly rejected in
  favor of solid shapes, because thin fading lines disappear at small icon sizes (16-32px) while
  bold flat shapes survive shrinking.
- Speed bars sit **behind** the box (an earlier "move to front" version cut across the blue field
  and was reverted).
- Box was shifted right (`translate(276 256)` skew center, box x=106 instead of 86) to give the
  longest speed bar's rounded cap room on the left — the original centered layout clipped that bar
  against the viewBox edge (x<0).
- Speed bars are weighted toward the bottom half of the icon (asymmetric fan, not symmetric
  top/middle/bottom) per explicit request.

## Generation pipeline

[assets/icon/make_icon.py](../../assets/icon/make_icon.py) re-implements the SVG geometry directly
in Pillow rather than rasterizing the SVG — no `cairosvg`/`resvg`/Inkscape available in this
environment (checked: not installed, `venv-gui` only has Pillow, no numpy). The skew is applied via
`Image.transform(..., Image.AFFINE, ...)` with hand-derived inverse-shear coefficients centered on
the box's own vertical middle; the diagonal blue gradient is a pure-Python per-pixel lerp (no
numpy); rounded speed-bar "pills" are drawn with `ImageDraw.rounded_rectangle` (radius = stroke
width / 2), which exactly reproduces SVG round-linecap horizontal lines.

Run `venv-gui/Scripts/python.exe assets/icon/make_icon.py` any time `app-icon.svg`'s geometry
changes (the two must be kept in sync by hand — the script does not read the SVG). Outputs:
- `assets/icon/png/icon-{16,24,32,48,64,128,256,512,1024}.png`
- `assets/icon/app-icon.ico` (multi-res: 16/24/32/48/64/128/256)

**ICO gotcha (fixed 2026-10-14):** Pillow's ICO writer only emits sizes <= the FIRST frame's size and
ignores `append_images`, so saving from the 16px frame produced a one-image 16x16 ICO (740 B) — the
desktop shortcut/exe icon was a blurry upscaled 16px. `make_icon.py` now writes the ICO by hand
(`write_ico`: header + directory + one PNG per size, each LANCZOS-resized from the 1024 master).
Verify any change with `Image.open(ico).info["sizes"]` — it must list 16..256. The exe/installer must
be rebuilt to pick it up ([[packaging]]), and Windows may keep the old icon in its cache until the
shortcut is re-created or `ie4uinit.exe -show` is run.

Wired in (see [[packaging]]): `vfast.spec` `icon=` + `datas`, `app.py` `iconbitmap`.

## Change log

- 2026-09-12 10:28: Created after locking the design and generating all sizes.
- 2026-10-14 18:14: Fixed the 16px-only ICO (hand-written multi-size ICO).
