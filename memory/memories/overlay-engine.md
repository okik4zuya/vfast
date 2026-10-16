---
name: overlay-engine
description: ffmpeg overlay/sensor engine (gui/core/overlay.py) — API, spec format, what was verified, and the handoff plan for the GUI Overlay panel (step 2)
metadata:
  type: project
  tier: T1
  created: 2026-10-14 14:40
  updated: 2026-10-16 08:04
---

# Overlay engine + plan for the Overlay panel

## Why this exists

User records the screen (vfast Screen Record), cuts in vfast (Cut panel), avoids CapCut (heavy).
Missing: add text/objects/censoring for a time range. Decided (2026-10-14 brainstorm): ffmpeg alone
is enough; build one engine, then a skill (step 1, chat-driven), then a GUI panel (step 2) as a thin
front end on the **same** engine — no second copy of the logic.

## Engine: `gui/core/overlay.py` (prototype, tested)

- `overlay_media(input, effects, output, log=print, preset="fast", crf=18, window=(a,b)|None)` —
  one `filter_complex` pass; `window` renders only that slice (test clips; times shifted back).
  Audio is stream-copied unless a `mute` effect exists (then AAC 192k). Output `yuv420p`.
- `preview_frame(input, t, png, effects=None, grid=False)` — single PNG at time `t` with the effects
  active at `t`; `grid=True` adds a 100px red grid with yellow x/y labels (for reading coordinates).
- `build_filter(...)` — pure function returning the filtergraph; the thing to unit-test.
- Uses `core.paths.ffmpeg_path`, `core.media.has_audio_stream`, `core.cut.parse_time`.

### Effect spec (list of dicts; times = seconds or `HH:MM:SS.mmm`, omitted = whole video)

| type | fields |
|---|---|
| box | x y w h [color=black] |
| blur | x y w h [strength=20] |
| pixelate | x y w h [block=16] |
| text | text x y [size=36] [color=white] [bg=e.g. black@0.7] [font=C:/Windows/Fonts/arial.ttf] |
| image | path x y [w] [h] (PNG with alpha) — **not tested yet** |
| mute | start end (audio only) |

Times are relative to the **input video**, so run overlay on the already-cut output (Cut first,
overlay second) or the timestamps drift.

## Verified (2026-10-14, on `~/Videos/recording_2026-09-11_193334_pembekalan-metnum.mp4`:
57 min, 1366x768, H.264 VFR avg ~26.5fps, AAC)

- box / blur / pixelate / text (Unicode `→ x²` fine) / mute all render correctly on a 30s window;
  mute confirmed by volumedetect (-48.5 dB vs ~-27 dB around it); frame preview + grid readable.
- Gotchas hit and fixed: `boxblur` chroma radius must be <= min(w,h)/4 (chroma plane is half size)
  — now capped automatically; `preview_frame` needs `-update 1` for single PNG output.
- Text goes through `textfile=` (UTF-8, temp dir) and `fontfile=` with `C\:/...` escaping — don't
  inline text into the filtergraph.

## Not done / open

- `image` effect untested; no fade in/out; no moving/tracked objects (static boxes only).
- No unit tests; no VFR normalisation (`fps=`) — hasn't caused A/V drift in the 30s test, unverified
  over the full 57 min. Full-length render time unmeasured (libx264 `fast`; NVENC `h264_nvenc` and
  `hevc_nvenc` exist in bin/ffmpeg.exe, none used by any core/*.py yet).
- Step 1 DONE (2026-10-14): skill `vfast-overlay` in `D:\coding\claude-skills\skills\vfast-overlay`
  (junctioned into `~/.claude/skills`); thin CLI `scripts/vfast_overlay.py` over this engine — see
  claude-skills memory `skill-vfast-overlay`. Spec format is shared: the panel should read/write the
  same `<name>.overlay.json`.

## Step 2 DONE (2026-10-14): `gui/panels/overlay.py`

**Layout redesigned same day (UI/UX pass):** left pane = watch only (video picker, mpv, transport);
right pane = edit: title, frame canvas on top (placeholder text until "Grab frame"), Grab/Preview bar,
"Effects (n)" header with a type menu "+ Add effect", accordion list (`EffectRow`: one-line summary,
only the selected row open; summary turns amber when region/text/file/time is missing; ⧉ duplicate, ✕
delete; ⏺ beside start/end takes the mpv time — the old left-pane Set Start/End are gone), Quality,
Output, `Spec ▾` (save/load), Test 10s, Run. Invalid fields get a red border and the bad row opens.
Canvas draws the selected region red, other geometry effects active at the frame time grey/dashed.
The paragraph below describes the first version; behaviour of drag/spec/render is unchanged.

Implemented as planned below, plus: `EffectRow` widget (type menu, start/end, fields wrapped at
`_LINE_PX`; switching type keeps same-named values), spec saved/auto-loaded as
`<video base>.overlay.json` next to the *input* video (`{"effects": [...]}`, same as the skill's
CLI), saved again before every render. Canvas "Grab frame" = clean frame, "Preview effects" = frame
with all effects baked in; drag converts canvas->video px via the scale factor; a plain click only sets
x/y (text/image anchor). Output `<base>_overlay.ext`; 10s test writes `<base>_overlay_test.ext` from
the mpv position. Verified headless with a generated 1280x720 clip (drag math exact, validation
message, spec round-trip, real windowed render, screenshot of layout). NOT verified: live Grab
frame/Set Start/10s test (need the mpv IPC position), real mouse drag, image effect via the panel.
Quirk: text color default is white, box black (carry-over hack in `_rebuild_fields`).

Original plan (kept for reference):

Panels are loaded dynamically by `gui/app.py` via `importlib.import_module()` and listed in
`gui/sidebar.py` — read both and an existing panel (`panels/cut.py` is the closest model) before
writing. Remember `vfast.spec` collects panels via `collect_submodules('panels')` (see [[packaging]]).

Reuse from the Cut panel ([[cut-panel-mpv-embed]]): video dropdown, `MpvEmbed` preview + transport
buttons, `Timeline`, the row-list pattern (`widgets/segment_row_list.py`), Fast/Balanced/High build
tiers (`_SPEED_TIERS` in `panels/cut.py`), output filename field, thread + log pattern.

Design decisions already reasoned out:
- **Drawing a rectangle over the mpv preview is not possible** — mpv is a foreign Win32 child HWND,
  Tk widgets cannot overlay it. Instead: button "Grab frame" -> `mpv_embed.get_time_pos_async` +
  `preview_frame(...)` -> show the PNG in a Tk `Canvas` (scaled to fit) where the user drags a box;
  convert canvas coords back to video pixels. That fills x/y/w/h of the selected effect row.
- Each effect = one row: type dropdown, start/end entries (+ "Set Start/Set End" from player, same
  as Cut), x/y/w/h or text fields depending on type, Delete. Fields should change with the type.
- "Preview" button = `preview_frame` at the chosen time with all effects (cheap), plus a
  "Render 10s test" using `window=`. "Run" = full `overlay_media`.
- Optional: save/load the spec as JSON next to the video, so the chat skill and the GUI can share
  the same file (the skill from step 1 is expected to use the same format).
- Keep `core/overlay.py` free of GUI imports; add effects there, not in the panel.
- Verify like earlier sessions: headless Tk test + a real screenshot; mark anything not
  click-tested as UNCONFIRMED in the todo list.

## Change log

- 2026-10-14 14:40: Created after the prototype engine passed its first real-video test.
- 2026-10-14 14:46: Step 1 (skill) done; recorded.
- 2026-10-14 14:46: Step 2 (panel) built and headless-verified; recorded.
- 2026-10-14 15:05: Panel re-laid out (canvas on top, accordion rows, ⏺ buttons, duplicate, inline validation).
- 2026-10-14 15:30: Effect-row ✕ is now the shared ghost delete + confirm (`widgets/delete_control.py`); ⧉ separated from it; field flow uses place() wrapping.
- 2026-10-16 07:00: Effects panel ([[effects-panel]]) reads `<video>.overlay.json` and runs `build_filter` inside its single render; overlay coords are absolute px, so Overlay must be applied before any layout change.
- 2026-10-14 15:57: Left pane now `widgets/video_pane.py` (shared with Cut/Trim); behaviour unchanged, regression test passed.
- 2026-10-16 08:04: Panel now autosaves/restores via core/overlayspec.py (see [[cut-trim-spec]]); the on-disk file gained `version`/`source` keys and may hold unfinished rows. Engine unchanged except new pure `effect_problem()`.
