---
name: trim-panel-redesign
description: Planned next step — rebuild the Trim panel on the Cut panel's layout (embedded mpv, ⏺ time capture) instead of the separate-mpv "Play in mpv" flow
metadata:
  type: project
  tier: T1
  created: 2026-10-14 15:30
  updated: 2026-10-14 15:36
---

# Trim panel -> Cut-style layout (DONE 2026-10-14, headless-verified, not click-tested)

**Built 2026-10-14.** `gui/panels/trim.py` rewritten: two-pane layout, shared `widgets/video_pane.py`, Start/End on two lines each with ⏺ (`_capture_single`), bulk rows via `SegmentRowList(on_capture=_capture_row)`; "Play in mpv" and the `core.play` import are gone. Verified headless with a mocked mpv time: capture -> entries + timeline, a real single trim and a real bulk trim both produced files, screenshot OK. Still UNCONFIRMED: real mpv time capture and click-through by the user. The plan text below is the original plan.

## Why
Trim still works the old way: "▶ Play in mpv" opens a *separate* mpv window (`core/play.py`) and the
user types times by hand. Cut/Overlay now pick times while watching the video inside the panel
(embedded `MpvEmbed`, transport buttons, ⏺ beside Start/End). User wants Trim to work the same.

## Current Trim (`gui/panels/trim.py`, single column, no panes)
- Single clip: `Timeline(mode="single")` + Start/End entries (`_on_field_change` / `_on_timeline_change`
  keep them in sync) + build-speed radios + output filename + Run Trim (`trim_video`).
- Bulk trim: `SegmentRowList(self)` (plain rows, no `on_capture`) + Run Bulk Trim (`bulk_trim`, one
  clip per row, output dir reported via `log_result`).
- Output name default is `trimmed_<base><ext>`; speed tiers dict duplicated from cut.py.

## Plan (mirror `panels/cut.py`, see [[cut-panel-mpv-embed]] and [[overlay-engine]] for the pattern)
- Two-pane `tk.PanedWindow` (400/345): left = video dropdown (no "Video:" label, no title) + `MpvEmbed`
  + transport buttons (48px) in a scrollable lower part; right (scrollable) = "Trim" title, Timeline,
  Start/End entries **each with a ⏺** that takes the mpv time (`mpv_embed.get_time_pos_async`),
  then bulk `SegmentRowList(..., on_capture=...)`, build speed, output, Run buttons.
- Drop "▶ Play in mpv" (and `core/play.py` import) from this panel.
- `MpvEmbed` is a foreign HWND: keep it in a non-scrolling container (CutPanel docstring explains);
  call `mpv_embed.set_aspect(media.width, media.height)` and `load()` on video change.
- Reuse `SegmentRowList(on_capture=...)`: compact rows, focus selects the row, ghost ✕ with confirm.
  Single-clip Start/End can stay two entries with ⏺ (or become row 1) — decide when building.
- Consider extracting the shared left pane (video menu + MpvEmbed + transport) into one widget now
  used by Cut, Overlay and Trim — three copies exist already.
- Verify like earlier sessions: headless Tk test (mock `get_time_pos_async`) + real screenshot; mark
  anything not click-tested UNCONFIRMED in the todo list.

## Change log
- 2026-10-14 15:30: Created from the user's request; nothing implemented yet.
- 2026-10-14 15:36: Implemented. Extracted `VideoPane` (video dropdown + MpvEmbed + transport + hint) and switched Cut and Overlay to it too; their regression tests still pass.
