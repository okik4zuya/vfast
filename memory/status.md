---
name: status
description: Living current-state narrative for vfast
metadata:
  type: project
  tier: T0
  created: 2026-09-11 10:48
  updated: 2026-10-16 08:30
---

# vfast — Status

## Current state

**v0.1.1 committed (2026-10-16).** HEAD `fee0053 v0.1.1` on top of `eed7371 Add Effects panel and per-video spec persistence
(Cut, Trim, Overlay, Effects)`; `gui/VERSION` = 0.1.1; working tree clean. Release notes for v0.1.1 were drafted in chat
(not stored in the repo).

Shipped in the code: Effects panel (21 presets / 25 packs, one ffmpeg pass with Overlay + speed + audio, live mpv preview,
Test 10s, `presets/vfx.py` CLI) - [[effects-panel]]; per-video spec persistence with a shared engine (`core/sidecar.py`) for
Cut, Trim, Overlay and Effects: `<video>.cut|trim|overlay|effects.json`, "Spec ▾" menu (Save writes beside the video without a
dialog, Load..., Reset), banner for specs that no longer fit the video - [[cut-trim-spec]]. Trim stores BOTH the single range
and the bulk rows in `<video>.trim.json`. Selected video is kept across panels (`App.selected_video`, [[ui-layout-pass]]).
80 unit/integration tests (`cd gui && ..\venv-gui\Scripts\python -m unittest discover -s tests -t .`) plus real-app scripts pass.

**Open:** nothing click-tested by the user (real mouse, real file dialogs, look strengths on real footage); `dist\vfast.exe` /
`vfast-setup.exe` not rebuilt for v0.1.1 as far as this memory knows (commands: pyinstaller gui\vfast.spec, then makensis
gui\installer.nsi - see [[packaging]]). Older open items are in [[todo-list]].

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
- 2026-10-14: Layout pass (collapsible sidebar, collapsed log console, fixed transport, capped preview) -
  [[ui-layout-pass]]; tab-switch speedup + loading overlay - [[panel-loading]]; Trim rebuilt on the Cut layout -
  [[trim-panel-redesign]]; Overlay panel - [[overlay-engine]]; blurry shortcut icon fixed (ICO had only 16px) and
  exe + `vfast-setup.exe` rebuilt - [[app-icon]], [[packaging]]. All headless/screenshot-verified, not click-tested.
- 2026-10-16: Effects panel + engine ([[effects-panel]]); selected video kept across panels; Cut/Trim/Overlay/Effects spec
  persistence on `core/sidecar.py` ([[cut-trim-spec]]); sidebar padding tightened so 13 buttons fit minsize 520.
