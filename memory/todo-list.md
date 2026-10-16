---
name: todo-list
description: Checklist of open tasks for vfast — no narrative
metadata:
  type: project
  tier: T0
  created: 2026-09-11 10:48
  updated: 2026-10-16 08:04
---

# vfast — To-Do

- [x] Design app icon (assets/icon/app-icon.svg) and generate all PNG/ICO sizes (assets/icon/make_icon.py) — see [[app-icon]]
- [x] Wire assets/icon/app-icon.ico into gui/vfast.spec (PyInstaller `icon=`) and set the customtkinter window icon in gui/app.py — see [[packaging]]
- [x] gui/: fix default project folder (`~/Videos`), add Open Folder button, mpv OSD millisecond
      clock, and dshow mic detection (inbox/ide.md items 1-4)
- [x] gui/: add arnndn (RNNoise) as a third Denoise method, bundling `bin/models/rnnoise-general.rnnn`
- [ ] Decide whether `legacy/vfast_v0.1.bat` .. `v0.7.bat` should be deleted or kept for reference
- [ ] Fix `yt2s` known bug: `generate_transcript.py` writes `shorts_transcription.json` to CWD instead of workspace (see yt2s/CLAUDE.md)
- [ ] Wire up `yt2s/core/clips.py` (`create_clips`) into the menu, or remove if abandoned
- [ ] Implement or remove `yt2s/core/execute.py` stub (`execute_flow` imported but never called)
- [x] gui/: Refresh button, task-completion log reporting (clickable path), Cut timeline active-range
      highlighting, Fast/Balanced/High-Quality build-speed tiers for Cut/Trim
- [x] gui/: Output filename field for Cut and Trim single-clip mode
- [x] gui/: fix Cut panel overflow past 5 remove-ranges hiding the Run Cut button (CutPanel is now
      a CTkScrollableFrame) — verified with a real screenshot
- [ ] gui/: manual GUI interaction pass (timeline drag handles, segment row list, Play in mpv,
      new Refresh/build-speed/output-filename controls, result-path Explorer click)
- [x] gui/: implement Cut panel embedded mpv preview (plan `in-gui-cut-panel-ancient-lerdorf.md`) —
      video confirmed rendering after fixing pack_propagate bug, see [[cut-panel-mpv-embed]]
- [x] gui/: Cut panel mpv-embed — fixed Set Start/End always overwriting the first remove range
      (SegmentRowList wasn't auto-selecting newly added rows) — see [[cut-panel-mpv-embed]] session 5
- [x] gui/: Cut panel mpv-embed — fix preview letterboxing by matching aspect ratio to the real
      video's dimensions (ffprobe) instead of a hardcoded 9:16 — needs user confirmation
- [x] gui/: Cut panel mpv-embed — move Timeline below the preview, Set End beside Set Start
- [x] gui/: Cut panel mpv-embed — layout confirmed OK by user (50:50 two-column split)
- [ ] gui/: Cut panel mpv-embed — added explicit transport buttons (play/pause, ±1s, ±5s) driven
      over the mpv IPC pipe instead of Win32 focus-forwarding; UNCONFIRMED by user click-test yet
      — see [[cut-panel-mpv-embed]] session 6
- [ ] gui/: Cut panel mpv-embed — decide whether to add Start<End validation (observed Start=17.3s/
      End=11.0s with no guard during manual testing; unconfirmed if this is the reported bug)
- [ ] gui/: Cut panel mpv-embed — run remaining plan verification steps (Shift+Right/Left seek,
      video-switch process cleanup, panel-switch cleanup, app-close cleanup, no orphaned mpv.exe)
- [ ] gui/: Cut panel mpv-embed — enabled native mpv OSC seekbar (always-visible, click-drag
      scrubbing); rendering verified via screenshot, drag-to-seek UNCONFIRMED by user click-test
      — see [[cut-panel-mpv-embed]] session 12
- [ ] gui/: test screen recording Start/Stop against a real microphone
- [x] gui/: run `pyinstaller gui/vfast.spec`, verify bundled bin/ resolves under frozen exe — see [[packaging]]
- [x] gui/: run `makensis gui/installer.nsi` — compiles clean; NOT yet click-tested install/uninstall on a clean machine
- [ ] gui/: fixed a packaging bug where Download panel's yt-dlp call would break in the shipped exe (frozen re-entry point added) — see [[packaging]]; retest Download panel inside an actually-installed copy, not just dist/vfast.exe
- [x] gui/: test Download panel against a real YouTube URL
- [x] gui/core/download.py: pass `--ffmpeg-location` (was silently skipping merges, unlike every other core/*.py module)
- [x] Upgrade stale yt-dlp in `venv/` (2026.2.4 → 2026.8.19) — this is the copy that actually runs (see [[gui-rewrite]] PATH note)
- [x] gui/core/download.py: stop relying on ambient PATH for `"yt-dlp"` — now uses `sys.executable -m yt_dlp`
- [x] gui/: Download panel — bulk URLs, quality/filesize selection, Stop button
- [ ] gui/: live-test the Download panel's Stop button against an in-flight download (terminate() path untested for real, only by pattern match to ScreenRecorder.stop())
- [ ] Consider adding a yt-dlp version/update check to the Download panel or a startup check, since YouTube extraction breaks on stale versions regularly and this repo has no pinning/update mechanism
- [x] gui/: fix frozen exe crashing with `ModuleNotFoundError: No module named 'panels'` (sys.path
      timing bug in `collect_submodules('panels')`) — see [[packaging]]
- [x] Rebuild `vfast-setup.exe` via `makensis gui/installer.nsi` — it still bundles the broken
      pre-panels-fix `dist/vfast.exe` from session 13
- [x] gui/core/overlay.py: ffmpeg overlay/sensor engine prototype (box/blur/pixelate/text/image/mute) tested on a real 57-min recording — see [[overlay-engine]]
- [ ] Overlay: test the `image` effect, fade in/out, and a full-length render (time + A/V sync on VFR input) — see [[overlay-engine]]
- [x] gui/: build the Overlay panel (step 2) — gui/panels/overlay.py, headless-verified — see [[overlay-engine]]
- [ ] gui/: click-test the Overlay panel for real (Grab frame needs live mpv position, Set Start/End, 10s test, drag on canvas, sidebar fit with 11 buttons at minsize 520) — UNCONFIRMED
- [x] Rebuild exe + `vfast-setup.exe` so the Overlay panel ships (pyinstaller --clean, then makensis)
- [ ] gui/: Cut panel — Set Start/End buttons replaced by ⏺ beside each Start/End field (`SegmentRowList(on_capture=...)`, row selected by focus, no Select button; Trim unchanged); headless-verified, UNCONFIRMED by user — see [[cut-panel-mpv-embed]]
- [ ] gui/: click-test the new ghost ✕ + delete confirmation in Cut, Trim and Overlay (real dialog; Trim's rows now also use ✕ instead of the Delete text button) — see [[cut-panel-mpv-embed]]
- [x] gui/: rebuild the Trim panel on the Cut layout (embedded mpv, ⏺ time capture, shared `widgets/video_pane.py`) — see [[trim-panel-redesign]]
- [ ] gui/: click-test Trim (real mpv ⏺ capture for single + bulk, Run Trim, Run Bulk Trim) and re-check Cut/Overlay after the VideoPane refactor — UNCONFIRMED
- [x] gui/: speed up tab switching + loading overlay (single cached ffprobe, off-thread warm-up, `App._show_panel` overlay) — see [[panel-loading]]
- [ ] gui/: click-test the loading overlay/spinner on a real folder with many videos; consider lazy widget build / deferred `mpv.load` for the remaining ~1 s in Cut/Trim/Overlay — see [[panel-loading]]
- [x] gui/: collapsible sidebar + collapsed-by-default log console + fixed transport/capped preview — see [[ui-layout-pass]]
- [ ] gui/: click-test the new sidebar (☰, Ctrl+B, icon tooltips), console auto-expand and vertical-video preview; fix the clipped "High Quality" radio in the Cut right pane — see [[ui-layout-pass]]
- [x] Fix blurry desktop-shortcut icon (ICO had only 16px) and rebuild exe + installer — see [[app-icon]]
- [ ] Verify the new icon in a real install (re-run `vfast-setup.exe`, re-create the desktop shortcut); installer also bundles the loading overlay + layout pass, not click-tested
- [x] gui/: Effects panel (21 presets, 25 packs, one-render pipeline with Overlay + speed + audio, per-video spec, live mpv preview, `presets/vfx.py` CLI, 45 tests) - see [[effects-panel]]
- [ ] gui/: click-test the Effects panel for real (checkbox/pack clicks, live preview in mpv, Test 10s, Render, switching videos, leaving and returning) and tune preset strengths on real footage - UNCONFIRMED, see [[effects-panel]]
- [ ] Rebuild exe + `vfast-setup.exe` so the Effects panel ships (pyinstaller --clean, then makensis); nothing from this session is committed yet
- [ ] gui/: move the duplicated `_SPEED_TIERS` in panels/trim.py, cut.py, overlay.py onto `core.render.SPEED_TIERS`
- [x] gui/: persist Cut and Trim specs per video with Save/Load by file name — see [[cut-trim-spec]]
- [ ] gui/: click-test Cut/Trim spec persistence with real mouse + real Save/Load dialogs — see [[cut-trim-spec]]
- [x] gui/: Overlay autosave/restore per video on the shared spec session (decided with the user) — see [[cut-trim-spec]]
