---
name: cut-trim-spec
description: Per-video spec persistence + explicit Save/Load for the Cut and Trim panels (<video>.cut.json / .trim.json), shared sidecar machinery, what was verified
metadata:
  type: project
  tier: T1
  created: 2026-10-16 07:47
  updated: 2026-10-16 08:04
---

# Cut / Trim spec persistence

## Why
Cut and Trim panels are destroyed on every navigation, so ranges typed in them vanished when switching panels.
Cut also leaked the previous video's rows into the next video (`if not rows: add default` only). Same
one-way flow as [[effects-panel]]: file -> session.spec -> widgets (inside `session.applying()`); widgets ->
spec only through `session.update`.

## Files
- `gui/core/sidecar.py` — `Schema`, `SpecSession` (switch_video, debounced atomic saves with write stamps,
  validation hook, `copy_from`, `export_to(path)` / `import_from(path) -> (ok, warnings)`), `read_sidecar`
  (corrupt/newer file -> moved to `.bak`), `source_changed`, `fingerprint`.
- `gui/core/segspec.py` — `CUT` (`<video>.cut.json`: `ranges` [[start,end]...] to REMOVE) and `TRIM`
  (`<video>.trim.json`: `start`,`end`,`bulk`; start/end `""` = whole video so the default follows the loaded
  video). Times stay the strings shown in the entries (half-typed values are never "fixed"); problems are
  reported by `validate_cut/validate_trim` (bad time, end<=start, start past the video end, end past it, file
  or resolution changed).
- `gui/widgets/spec_bar.py` — `SpecBanner` (amber notice + Keep spec), `spec_menu` ("Spec ▾": Save spec / Load spec... /
  Reset spec), `new_session`, `ask_load_path`. **Save spec has no dialog**: it writes `<video base>.cut.json` (resp. .trim/.effects)
  right next to the video; only Load asks for a file.
- Panels: `_sync_widgets` (spec -> widgets), `_persist` (widgets -> spec; also called in `_on_video_change`
  before switching and in `destroy()` so typing that never got a FocusOut is kept), `_show_issues`.
- Build-speed radio now remembered in settings (`cut_quality`, `trim_quality`).

## Rules worth remembering
- A lone Cut row still showing the default range (0 -> min(5s, duration)) is NOT saved; the default is computed
  from the spec's video (`session.video`), not the dropdown's, because during a switch the rows still belong to
  the video being left.
- Trim end == video end is stored as `""`.
- Loading a spec takes the settings only, never the file's source stamp; an unusable file changes nothing and
  is never renamed. A Trim file loaded into Cut (or vice versa) is harmless: unknown fields are dropped.
- Switching video never refuses (unlike Effects, nothing blocks while a Cut/Trim job runs: workers use args
  captured at click time).

## Verified (2026-10-16)
- 68 tests total (18 new in `tests/test_segspec.py`); real app driven headless: Cut and Trim restore after
  leaving the panel, no leak between videos, uncommitted typing saved on leaving, Save/Reset/Load by file name,
  banner for a range beyond the video end (screenshot), Effects regression scripts unchanged (22/22, pack 9/9).
- NOT verified: real mouse clicks / real file dialogs (the scripts replace `ask_save_path`/`ask_load_path`),
  timeline drag persistence beyond the code path (`_on_timeline_change` calls `_persist`).
- The same "Spec ▾" menu (top right of the pane, beside the title; Save spec / Load spec... / Reset spec) is now in Cut, Trim,
  Effects and Overlay. Effects: Reset moved from the bottom row into the menu (Copy from... stays).
- **Overlay is on the same engine too** (`core/overlayspec.py`, `OverlaySession`): autosave to `<video>.overlay.json`, restored after
  leaving the panel / switching video, banner, Reset (asks to confirm). The file stays compatible with the `vfast-overlay` skill CLI and
  Effects (they read only `effects`; version-less and bare-list files still load via `Schema.list_key`). Rows are saved as shown,
  **including half-finished ones** (`clean_effect`: empty values dropped, numbers as numbers); `core.overlay.effect_problem` says which
  are not renderable yet, the Overlay banner lists them, and Effects/`vfx.py --overlay` skip them (`spec.usable_overlay`) and say so.
  The Overlay quality radio is remembered (`overlay_quality`). Overlay's own Run still validates through `collect_effects` (red field).

## Change log
- 2026-10-16 07:47: Created.
- 2026-10-16 07:56: Save spec is dialog-free (next to the video); Spec menu added to Effects; Overlay's menu moved to the header. Real-app scripts: Cut/Trim 28/28, Effects spec 6/6.
- 2026-10-16 08:04: Overlay moved onto the shared session (autosave/restore/banner), `effect_problem`, Effects skips unfinished overlay rows. 80 tests; real-app scripts: Overlay 20/20.
