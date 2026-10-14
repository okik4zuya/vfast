---
name: status
description: Living current-state narrative for vfast
metadata:
  type: project
  tier: T0
  created: 2026-09-11 10:48
  updated: 2026-10-14 18:18
---

# vfast — Status

## Current state

**Layout pass (2026-10-14, latest) — see [[ui-layout-pass]].** Collapsible icon sidebar (☰/Ctrl+B), log console collapsed by
default with badge + auto-expand, transport row fixed under the preview, vertical-video preview height-capped.
Screenshot-verified, not click-tested.

**Tab-switch speedup + loading overlay (2026-10-14) — see [[panel-loading]].** Cut/Trim/Overlay were
slow because every tab click ran 2 serial uncached ffprobes per video on the Tk thread; now one cached,
parallel probe warmed off-thread in `App._show_panel`, with a spinner overlay. Headless-verified, not click-tested.

**Earlier today:** Trim rebuilt on the Cut layout with shared `widgets/video_pane.py` ([[trim-panel-redesign]]);
Overlay panel + ⏺ capture + ghost ✕ delete confirm across Cut/Trim/Overlay ([[overlay-engine]],
[[cut-panel-mpv-embed]]). All headless-verified, none click-tested by the user.

**Icon + build (2026-10-14 18:18):** the blurry shortcut icon was an ICO containing only 16px (Pillow bug) — fixed in
`make_icon.py`, exe + `vfast-setup.exe` rebuilt with all of today's changes ([[app-icon]], [[packaging]]).
**Open:** older Cut items unconfirmed; new icon/installer not yet checked in a real install.

Earlier state (GUI rewrite, Cut mpv embed sessions 1-11, icon, NSIS packaging) is archived below and in
[[gui-rewrite]], [[cut-panel-mpv-embed]], [[app-icon]], [[packaging]].

## Archive

- 2026-09-11: Memory system freshly scaffolded, adapting only ARTi's `memory/` folder convention —
  this is a Windows video-processing tool repo, not an ARTi research/manuscript project, so no
  idea/writing/literature/submission folders or `arti-db` project registration were created.
- 2026-09-12 (sessions 1-5): Built the Cut panel's embedded mpv preview end-to-end (new
  `mpv_ipc.py`/`mpv_embed.py`, `CutPanel` restructure, aspect-matching, layout redesigns) and fixed
  several real bugs along the way (invisible preview from a `pack_propagate`/`grid_propagate`
  mismatch, layout overflow hiding controls, `SegmentRowList` not auto-selecting new rows). Also
  shipped Refresh button, task-completion log reporting, Cut timeline active-range highlighting,
  build-speed tiers, output-filename fields, closed 4/5 `inbox/ide.md` items (project folder, Open
  Folder button, mpv OSD clock, dshow mic detection), added arnndn denoise, and verified the
  Download panel end-to-end against real YouTube URLs. Full session-by-session detail archived in
  [[cut-panel-mpv-embed]] and [[gui-rewrite]] — not repeated here to keep this file from growing
  unbounded; see those files' own change logs for the history.
- 2026-09-12 (sessions 6-14): Cut panel transport buttons + keybindings, relative+exact seek fix,
  width-driven preview + draggable sash, scrollable left pane + Home/End; locked app icon wired into
  build; NSIS installer built; frozen-exe `panels` import fix (`sys.path.insert` before
  `collect_submodules`). Detail in [[cut-panel-mpv-embed]] and [[packaging]].
- 2026-10-14: Overlay engine prototype (`core/overlay.py`) + `vfast-overlay` skill; see [[overlay-engine]].
