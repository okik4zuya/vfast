---
name: memory-index
description: Index of vfast project memory files — pointers only
metadata:
  type: project
  tier: T0
  created: 2026-09-11 10:48
  updated: 2026-10-16 08:04
---

# vfast — Memory Index

- [repo-overview.md](memories/repo-overview.md) — what vfast is, subproject layout, known issues
- [gui-rewrite.md](memories/gui-rewrite.md) — customtkinter GUI in gui/: architecture (+ later panels/widgets: Overlay, VideoPane, delete_control), verified vs. not, Download panel history, inbox/ide.md debug fixes, Denoise arnndn addition
- [cut-panel-mpv-embed.md](memories/cut-panel-mpv-embed.md) — Cut panel embedded mpv preview: architecture, IPC transport controls, open items — own change log has full session history
- [app-icon.md](memories/app-icon.md) — locked app icon SVG design + Pillow-based PNG/ICO generator (now wired in, see [[packaging]])
- [packaging.md](memories/packaging.md) — PyInstaller + NSIS build pipeline, verified end-to-end incl. yt-dlp frozen-mode fix
- [overlay-engine.md](memories/overlay-engine.md) — ffmpeg overlay/sensor engine (core/overlay.py): API, spec, tested results, plan for the GUI Overlay panel (step 2)
- [trim-panel-redesign.md](memories/trim-panel-redesign.md) — Trim rebuilt on the Cut layout (embedded mpv + ⏺ capture, shared VideoPane); plan + what was verified
- [panel-loading.md](memories/panel-loading.md) — why tab switches were slow (2 serial ffprobe/video, uncached, main thread) + cached probe, off-thread warm-up, loading overlay
- [effects-panel.md](memories/effects-panel.md) — Effects panel: one-render pipeline (presets/packs + Overlay + speed + audio), per-video spec persistence, live mpv preview, CLI, tests
- [cut-trim-spec.md](memories/cut-trim-spec.md) — per-video spec persistence for Cut/Trim/Overlay (+Effects): shared sidecar session, Spec ▾ save/load, banner
- [ui-layout-pass.md](memories/ui-layout-pass.md) — collapsible sidebar (Ctrl+B), collapsed-by-default log console, fixed transport + capped mpv preview, settings.json prefs

## Change log

Per-session detail lives in each memory file's own change log (see files above and [[status]]'s
Archive), not here — this index only tracks when it was last reorganized.

- 2026-10-16 07:47: Added [[cut-trim-spec]] pointer.
- 2026-10-16 07:00: Added [[effects-panel]] pointer.
- 2026-10-14 18:10: Added [[ui-layout-pass]] pointer.
- 2026-10-14 17:55: Added [[panel-loading]] pointer.
- 2026-09-12 09:10: Compacted this file's change log (had grown to dominate the file, duplicating
  detail already in [[gui-rewrite]] and [[cut-panel-mpv-embed]]'s own change logs).
