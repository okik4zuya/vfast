---
name: panel-loading
description: Why Cut/Trim/Overlay tabs were slow to open and the fix - cached single-ffprobe media scan, off-thread warm-up, loading overlay in App._show_panel
metadata:
  type: project
  tier: T1
  created: 2026-10-14 17:55
  updated: 2026-10-14 17:55
---

# Panel switch latency + loading overlay (2026-10-14, headless-verified, not click-tested)

## Cause
`App._show_panel` destroyed/rebuilt the panel synchronously on the Tk thread, and each panel's
`list_videos()` ran **2 serial ffprobe processes per video** (duration, then dimensions), uncached,
on every tab click. Cut/Trim/Overlay additionally build heavy CTk widgets and launch embedded mpv.
The clicked tab was only highlighted at the very end, so the UI looked frozen.

## Fix
- `gui/core/media.py`: one ffprobe call (`-of json`, duration + v:0 size), module cache
  `_PROBE_CACHE` keyed `(abspath, mtime, size)` (failures not cached), 4-thread pool,
  optional `progress(done,total)` callback on `list_videos/list_audios`. Probe-dims flag removed.
- `gui/app.py` `_show_panel`: highlight tab + destroy old panel immediately (kills embedded mpv,
  whose native HWND would paint over the overlay) -> warm the cache in a thread -> build panel
  (its own `list_*` calls now hit the cache). Overlay (`self.loading`, spinner via `after(80)`,
  "Loading videos (i/n)...", cursor `watch`) appears only if the scan outlasts 150 ms.
  `_nav_token` discards superseded loads. Cut/Trim/Overlay (`_HEAVY_PANELS`) also get a static
  "Opening ..." overlay during the unavoidable ~1 s main-thread build.
- No panel code changed; every panel benefits.

## Measured (6 tiny test videos)
cold scan 0.30 s, warm 0.002 s; panel build ~0.4 s + first update ~0.4 s (CTk widgets + mpv Popen) -
this remainder is still on the Tk thread and is the next lever (lazy-build sections, defer mpv.load
with `after`). One cold first-click took 9.7 s once and did not reproduce (likely AV/first import).

## Open
- Not click-tested by the user; real folders with many/long videos untested.
- Cache is in-memory only (lost on exit); persisting to a JSON in the project folder is possible.

## Change log
- 2026-10-14 17:55: Created after the analysis + implementation session.
