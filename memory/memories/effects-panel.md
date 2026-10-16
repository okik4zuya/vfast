---
name: effects-panel
description: Effects panel + engine (core/effects.py, render.py, spec.py): single-render design, per-video spec persistence, live mpv preview, what was verified vs not
metadata:
  type: project
  tier: T1
  created: 2026-10-16 07:00
  updated: 2026-10-16 07:47
---

# Effects panel (single-render effects + overlay + speed + audio)

## Why
Each vfast tool wrote a new file (Cut -> Overlay -> Denoise -> Speed = 4 re-encodes). The Effects panel
applies presets/packs + the saved Overlay effects + speed + audio cleanup in **one** ffmpeg process.
Decided with the user: scope = Effects + Overlay + Speed in one render (Cut/Trim stay separate: Cut is
render 1 only when something is removed); preview = live in mpv.

## Files
- `gui/core/effects.py` — `PRESETS` (21), `PACKS` (25, flat lists), `normalize()` (expand packs, drop unknown,
  dedupe, one layout), `build_chain()` (pure; tracks frame size so `zoompan` gets the right `s=`/fps and the
  logo is 15% of the *final* frame), `preview_filters()`.
- `gui/core/render.py` — `build_command()` (pure), `render()`, `run_ffmpeg()`, `SPEED_TIERS`.
- `gui/core/spec.py` — Effects schema + `EffectsSession`; the generic machinery moved to `gui/core/sidecar.py` (`Schema`, `SpecSession`, read/write, explicit `export_to`/`import_from`) and is shared with Cut/Trim, see [[cut-trim-spec]].
- `gui/panels/effects.py` — thin view. `MpvEmbed.load(vf=, af=)`, `set_filters`, `set_speed` added.
- `presets/vfx.py` + `vfx.ps1` — CLI over the same engine (replaced the old standalone PowerShell logic,
  which had a wrong logo size and a fixed-1080p/30fps zoom).
- `gui/tests/` — `python -m unittest discover -s tests -t .` from `gui/` (45 tests, ~40 s; uses `venv-gui`).

## Graph order (one filtergraph)
overlay effects (input pixels/timeline) -> layout (vertical/square/hd) -> look -> zoom -> caption ->
watermark -> `setpts` (speed) -> fade (timed on the sped-up length). Audio: overlay mute -> voice cleanup ->
`atempo` -> loudnorm -> afade. Overlay must precede layout because its x/y are pixels of the input.

## Persistence / video switching (user's hard requirement: clean, no leakage)
- Sidecar `<video base>.effects.json` (note: base without extension, like `.overlay.json`); fields presets,
  params, speed, use_overlay, pack, source fingerprint. `.overlay.json` stays the single source for Overlay.
- Panel is destroyed on every navigation -> `destroy()` flushes. Widgets are only a view: spec -> widgets via
  `_sync_widgets` inside `session.applying()`; widgets -> spec only through `session.update`.
- `switch_video`: refused while rendering; flushes old; bumps `generation` (stale async probes ignored);
  missing file = defaults (never copy of previous video); stale debounce timers can't overwrite newer data
  (write stamps — a mutation test proves the guard is exercised).
- Validation shows, never silently fixes: file changed, resolution changed (Overlay coords are absolute px),
  no audio (audio presets disabled), overlay effect starting after the video ends. Default spec = no file.

## Verified (2026-10-16)
- 45 unit/integration tests; all 25 packs render; the full combo (overlay blur/text/mute + shorts + caption +
  watermark + zoomin + speed 2x) = exactly 1 ffmpeg process, 1080x1920, duration halved.
- Every preset's live graph accepted by the bundled mpv (`--vf=lavfi=graph=%N%...`, strict: any warning = fail;
  negative control caught). IPC `set_property vf/af/speed` works on a running mpv.
- Real app driven headless (`App` + panel, scripts were in the session scratchpad): pack/preset clicks,
  exclusive layout, switch a<->b clean, restore after leaving the panel, render busy-lock, Test 10s,
  screenshots incl. minsize 760x520 (sidebar needed tighter button padding for 13 buttons).

## Not verified / caveats
- **No real mouse click-test by the user.** Preset strengths (saturation 1.2, vignette PI/6...) judged only on
  synthetic video + one frame; tune on real footage in `effects.PRESETS`.
- mpv answers `success` to `set_property vf` even for a graph it later rejects -> live graphs must stay
  known-good (tests cover all presets; a bad *caption path* is the only runtime variable, it uses a textfile).
- Live preview excludes overlay effects, logo, speed audio pitch and fade (use Test 10s). `zoompan` is jittery
  by nature and slow on long clips. Output defaults to `.mp4`; `+faststart` only for mp4/mov/m4v.
- Quality tiers duplicated in Trim/Cut/Overlay panels (`_SPEED_TIERS`); Effects uses `core.render.SPEED_TIERS`.
- Not committed; exe/installer not rebuilt (Effects not in `vfast-setup.exe` yet).

## Change log
- 2026-10-16 07:00: Created. Engine, spec session, panel, sidebar entry, CLI wrapper, tests, README row.
- 2026-10-16 07:26: Chosen pack now persists (`spec['pack']`); the dropdown shows it only while the ticked presets still equal the pack (`spec.effective_pack`), so hand-editing falls back to the placeholder and restoring brings it back. Reported by the user; 5 new tests (50 total) + real-panel check.
- 2026-10-16 07:47: Spec machinery generalized into core/sidecar.py (Effects behaviour unchanged, all 27 spec tests + the real-panel scripts still pass); Cut/Trim now use it.
