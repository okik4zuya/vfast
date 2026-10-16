---
name: status
description: Living current-state narrative for vfast
metadata:
  type: project
  tier: T0
  created: 2026-09-11 10:48
  updated: 2026-10-16 08:04
---

# vfast — Status

## Current state

**Effects panel built and headless-verified (2026-10-16) — see [[effects-panel]].** New sidebar tab "Effects":
21 presets / 25 packs (YouTube x8, Shorts/TikTok/Reels, Instagram, WhatsApp, looks, quick fixes) rendered
together with the saved Overlay effects, speed and audio cleanup in **one** ffmpeg pass, with live mpv preview
and a per-video `<video>.effects.json` that survives panel switches and video changes without leaking
(`core/effects.py`, `render.py`, `spec.py`, `panels/effects.py`; CLI in `presets/vfx.py`). 45 tests pass; the real
app was driven headless incl. render, Test 10s and minsize 760x520.
**Cut/Trim spec persistence (2026-10-16 07:47) — see [[cut-trim-spec]].** `<video>.cut.json` / `<video>.trim.json` restore the ranges after leaving a panel or switching video (no leak), with a "Spec ▾" menu (Save writes beside the video without a dialog; Load/Reset), the same menu now in Effects and Overlay; **Overlay also autosaves/restores per video** (`core/overlayspec.py`; file stays CLI/Effects compatible, may contain unfinished rows which Effects skips) and a banner for specs that no longer fit the video; shared engine `core/sidecar.py` (Effects moved onto it). 68 tests + real-app scripts pass; not click-tested.

**Also (2026-10-16 07:19):** the selected video is now remembered across panels (`App.selected_video`, [[ui-layout-pass]]).
**Open:** no real mouse click-test or look tuning on real footage; exe/installer not rebuilt; nothing committed.
Older open items (Cut/Trim/Overlay click-tests, new icon in a real install) are in [[todo-list]].

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
