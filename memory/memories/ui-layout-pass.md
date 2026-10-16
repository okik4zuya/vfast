---
name: ui-layout-pass
description: Collapsible sidebar (icon mode, Ctrl+B), collapsed-by-default log console with auto-expand, fixed transport row and height-capped mpv preview in VideoPane; persisted prefs in core/settings.py
metadata:
  type: project
  tier: T1
  created: 2026-10-14 18:10
  updated: 2026-10-16 07:19
---

# Layout pass: console, transport, sidebar (headless-verified + real screenshots, not click-tested)

## Problem
Default 200 px console left ~380 px for the panel; VideoPane stacked dropdown + preview + transport,
with transport inside a scroll area -> clipped (even for 16:9), absent for vertical video (preview = 1.78x width).

## What changed
- **Console** (`gui/log_console.py`): starts collapsed (32 px). Header shows the last line + "● N" unread badge.
  Auto-expands on `write_result` or a line matching error/failed/failure/traceback/gagal (word-bounded).
  Only the user's own Hide/Show click persists (`console_expanded`); auto-expand is transient.
- **VideoPane** (`widgets/video_pane.py`): transport row now in the fixed `top` frame (equal-weight shrinkable
  columns); only the hint scrolls. On `<Configure>` it computes a preview height cap and calls
  `MpvEmbed.set_max_height`.
- **MpvEmbed** (`widgets/mpv_embed.py`): surface is `place`d, not packed. Capped => frame height = cap and
  surface narrowed to `h/aspect`, centered (no mpv pillarbox). GOTCHA: `place()` options accumulate -
  always pass `width=""/height=""` (or `relwidth=""`) when switching modes, else width adds to relwidth.
  GOTCHA: CTkFrame `<Configure>` events come from its internal canvas, so don't test `event.widget is self`.
- **Sidebar** (`gui/sidebar.py`): ☰ in topbar + Ctrl+B (ignored while an Entry/Text has focus, where Tk's own
  Ctrl+B moves the cursor). Collapses 160 -> 56 px to icon-only (emoji, size 18) with hover tooltips
  (`widgets/tooltip.py`). No animation on purpose (mpv refits on every width change). Persists `sidebar_collapsed`.
- `gui/core/settings.py`: tiny JSON store in `%APPDATA%/vfast/settings.json`; env `VFAST_SETTINGS` overrides
  the path (tests must set it).

## Verified
Screenshots at 960x680: 16:9 and vertical video both keep the full transport row visible; vertical preview
is capped (424 px) and centered; icon sidebar renders. All 11 panels build; Ctrl+B, persistence across a
restart, badge/preview text, auto-expand on error/result and no false positive on "errors=0" all checked.

## Open
- Not click-tested by the user (tooltips, real Ctrl+B with focus in entries, emoji glyphs on their font set).
- Pre-existing: right pane clips the "High Quality" radio at ~345 px width (visible in screenshots).
- Pre-existing: screen_record's device-scan thread calls `app.after` from a worker (fails only outside mainloop).

## Change log
- 2026-10-14 18:10: Created; implemented console/transport/preview-cap/sidebar after the proposal discussion.
- 2026-10-16 07:19: Selected video now survives panel switches: `App.selected_video` + `App.preferred_video(videos)`; every panel with a video dropdown (Speed, Add/Remove/Extract Audio, Denoise, Trim, Cut, Overlay, Effects) restores it in `_refresh_files` and records it in `_current_video`. Falls back to the first video if it is gone; `set_project_dir` clears it. Merge (multi-select) is unchanged. Verified by driving the real app across all 9 panels.
