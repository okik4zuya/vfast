---
name: cut-panel-mpv-embed
description: In-panel embedded mpv preview for the Cut panel — architecture, CustomTkinter/Tk propagation bugs, IPC-based transport controls, and what's still open
metadata:
  type: project
  tier: T0
  created: 2026-09-12 07:47
  updated: 2026-10-14 15:57
---

# Cut panel: embedded mpv preview

Implements plan `C:\Users\user\.claude\plans\in-gui-cut-panel-ancient-lerdorf.md`: play video
with audio *inside* the Cut panel (not a separate mpv window), scrub with mpv's own keybindings,
click "⏺ Set Start"/"⏺ Set End" to capture mpv's current position into the active range row.

## New files

- **`gui/core/mpv_ipc.py`** — one-shot Windows named-pipe JSON IPC (`send_command`,
  `query_property`). No new pip dependency: plain `open(pipe, "r+b", buffering=0)` works for named
  pipe clients on Windows via `CreateFileW`. Retries opening the pipe every 100ms up to a deadline
  (covers the race between `Popen()` and mpv binding `--input-ipc-server`).
- **`gui/widgets/mpv_embed.py`** — `MpvEmbed(CTkFrame)`, hosts a plain `tk.Frame` "surface" that
  mpv attaches to via `--wid=<winfo_id()>`. Owns process lifecycle (`load`/`stop`/`is_running`),
  one-shot async position queries (`get_time_pos_async`), and fire-and-forget IPC commands
  (`send_command_async`, `toggle_pause`, `seek_relative`).

## `gui/panels/cut.py` layout (current, as of session 10 — superseded the earlier fixed-grid split)

A `tk.PanedWindow(orient="horizontal")` with a user-draggable sash, not a plain grid column split —
see Session 10 below for why. `bg` is queried at build time from `self.winfo_toplevel().cget("bg")`
so the plain-Tk PanedWindow's sash area matches the app's real (CTk-managed) background instead of
Tk's own default gray.

- **`left`** contains two stacked children, not one flat frame (added in session 11 — see below):
  `left_top` (row 0, `sticky="new"`, **not** scrollable — a foreign HWND can't live inside a
  `CTkScrollableFrame`'s `Canvas`, see Bug 2 below) holds header, video dropdown, `MpvEmbed`; below
  it, `left_scroll` (row 1, `CTkScrollableFrame`, `sticky="nsew"`, `left.grid_rowconfigure(1,
  weight=1)`) holds the transport button row (⏮Start / ⏪5s / ◀1s / ⏯ / 1s▶ / 5s⏩ / End⏭), Set
  Start/Set End, and the keybinding hint — this is what scrolls once its own content overflows
  whatever room `left_top` leaves it. Added via `paned.add(left, minsize=260, width=560,
  stretch="always")` — `width=560` only sets the *initial* pane size (video pane larger by default,
  per user preference); the sash drag or a window resize is what determines it after that.
- **`right`** (`CTkScrollableFrame`): Timeline, remove-ranges list, speed radios, output filename,
  Run Cut button. **Gotcha:** `CTkScrollableFrame` draws itself on an internal canvas one level
  below the widget passed as `master` — the actual direct Tk child of `paned` is
  `right._parent_frame`, not `right` itself. `paned.add(right, ...)` raises `TclError: can't add
  ... to ...` since `right`'s real parent in the Tk tree is a canvas, not `paned`; must be
  `paned.add(right._parent_frame, minsize=220, stretch="always")` instead.

## Bug 1 (framework landmine, not the root cause): `CTkFrame.bind()` silently redirects to an internal canvas

`customtkinter/windows/widgets/ctk_frame.py:185`:
```python
def bind(self, sequence=None, command=None, add=True):
    """ called on the tkinter.Canvas """
    self._canvas.bind(sequence, command, add=True)
```
Every `CTkFrame`-derived widget draws itself via an internal decorative `tkinter.Canvas`, so
`.bind("<Configure>", ...)` on one silently binds that canvas, not the real frame. Usually harmless
here since the canvas tracks the frame's size 1:1, but worth knowing before debugging any future
`<Configure>`/`<Destroy>` binding issue on a `CTkFrame`-derived widget.

## Bug 2 (the actual root cause of an invisible/1px preview): `grid_propagate(False)` does nothing for a `pack()`-managed child

`MpvEmbed` originally called `self.grid_propagate(False)`, but `self.surface` (the mpv attach
target) is placed with `.pack(...)`, not `.grid(...)` — the two propagate flags are independent per
geometry manager. Result: `winfo_reqheight()` correctly reported the configured height, but the
*actual* HWND geometry stayed collapsed at ~1px forever, because `pack_propagate` (left at its
default `True`) kept re-shrinking the frame to its child's natural ~1×1 size on every geometry pass.
**Lesson:** `winfo_reqheight()` matching what you set is not proof of the real on-screen size —
check `winfo_height()`/real HWND `GetClientRect` too, and match `pack_propagate`/`grid_propagate`
to whichever geometry manager actually placed the children. **Fix:** use `pack_propagate(False)`.
Diagnosed via a standalone ctypes script (`EnumChildWindows`/`GetClientRect`/`GetWindowRect`) —
reusable technique for any future native-window-embedding bug in this repo; don't trust screenshots
alone for sub-pixel-scale layout bugs.

## Bug 3 (kept, unconfirmed necessity): `--d3d11-flip=no`

Added to the mpv launch command to work around the Windows "airspace problem" (D3D11 flip-model
swap chains aren't reliably clipped to a parent HWND under `--wid`). Never re-tested with the flag
removed after Bug 2 was fixed, so it's unconfirmed whether it was ever actually necessary — safe to
try removing if the mpv command line ever needs simplifying (re-verify with the ctypes technique
above, not eyeballing).

## Sessions 2-7 summary (2026-09-12, condensed 2026-09-12 08:34)

Iterative loop across six sessions on two fronts:

- **Layout:** fixed an overflow bug (a non-scrolling region taller than the whole panel, making
  controls unreachable) -> two-column mockup approved -> widened to a true 50:50 split -> user
  confirmed this layout is **OK, resolved, no longer needs re-checking**.
- **Playback control:** repeatedly tried to give the embedded mpv HWND real Win32 keyboard focus
  (`SetFocus`, then `SetFocus`+`AttachThreadInput` to work around per-thread input queues) — **never
  confirmed working across 3 sessions**. Session 6 abandoned that approach entirely in favor of
  driving mpv over the existing IPC pipe (`send_command_async`/`toggle_pause`/`seek_relative`),
  wired to explicit transport buttons plus keybindings on `MpvEmbed.surface` (Tk-level same-process
  focus via `focus_set()`, sidestepping the cross-process OS-focus problem completely). The old
  `_focus_mpv`/`SetFocus`/`AttachThreadInput` code is still in `mpv_embed.py`, harmless, unused.
- **Other real bugs fixed along the way:** `segment_row_list.py`'s `add_row()` only auto-selected
  the *first* added row, silently leaving Set Start/End pinned to range 1 for every later range
  (fixed by dropping an `is None` guard); black-bar letterboxing from a hardcoded 9:16 aspect
  regardless of actual video dimensions (fixed via ffprobe-based `set_aspect()`, still unconfirmed
  against a real video); a session-6 keybinding mapping had the 1s/5s seek amounts backwards
  (fixed session 7); a hint label briefly covered the transport buttons (fixed by relocating it).

## Session 8 (2026-09-12): root-caused and fixed the wrong-seek-distance bug

User reported the IPC-based transport controls (from session 6) move the wrong amount: a 1s
nudge moves ~10s, a 5s nudge moves ~5-10s. **Root cause:** `seek_relative()` sent
`["seek", seconds, "relative"]` — plain `"relative"` (no `exact` flag) is mpv's fast/imprecise
*keyframe* seek mode, which snaps to whichever keyframe is nearest instead of the literal offset.
On web-sourced video with keyframes spaced ~5-10s apart, a 1s or 5s request lands wherever the
nearest keyframe happens to be, which looks exactly like "1s moves ~10s, 5s moves ~5-10s" —
consistent with keyframe spacing, not a wrong seek amount in the code (the button/keybinding
values −5/−1/1/5 were already correct). **Fix (`gui/widgets/mpv_embed.py`):** changed the command
to `["seek", seconds, "relative+exact"]`, forcing frame-accurate seeking. **User confirmed working
in session 9.**

## Session 9 (2026-09-12): fixed maximize-window pillarboxing — preview no longer stretches to full column width

User confirmed session 8's seek fix works. New report: at the default window size the preview's
size/aspect is correct, but maximizing the window widens the left column and the video frame grows
black bars — the preview wasn't shrinking/growing correctly with the window.

**Root cause:** `MpvEmbed` was gridded with `sticky="ew"`, always stretching to the column's full
width; height was then derived from that width but capped at a fixed `max_height` (220, set once at
construction). At the default window size `width * aspect <= 220` so the box's aspect happened to
match the video's. Maximizing widens the column a lot, `width * aspect` blows past 220, height stays
capped at 220 — so the on-screen box becomes wider than the video needs and mpv pillarboxes
(black bars on the sides) inside the mismatched box. This is the same *class* of bug as the old
`_ASPECT = 9/16` hardcoding from session 5 (container aspect not matching video aspect), just
triggered by window resizing instead of a wrong constant.

**Fix (`gui/widgets/mpv_embed.py`):** replaced the width-driven/height-capped model with
`fit(avail_width, avail_height)`, which computes the *largest box that fits within both dimensions*
while preserving `_aspect` exactly (binds on whichever dimension is the tighter constraint), then
explicitly sets both `width` and `height` via `self.configure(...)`. Removed the old
`max_height`-ceiling logic, the constructor's now-dead `max_height` bookkeeping, and the self-bound
`<Configure>` handler that just watched the widget's own (externally-forced) width.

**Fix (`gui/panels/cut.py`):** `mpv_embed.grid(row=3, column=0)` — dropped `sticky="ew"` so the
widget isn't forced to full column width and Tk centers it in the cell once `fit()` gives it an
explicit (possibly narrower) size. Added `left.bind("<Configure>", self._on_left_resize)`: `left`
fills the whole column (sticky="nsew"), so its `<Configure>` fires on every window resize;
`_on_left_resize` computes `other_rows_height = left.winfo_reqheight() - mpv_embed.winfo_reqheight()`
(everything in the column except the preview) and calls `mpv_embed.fit(event.width, event.height -
other_rows_height)` — i.e., the preview claims the column's full width and whatever vertical room is
left after the header/dropdown/buttons/hint, always re-fit to the video's exact aspect.

**Superseded before the user ever saw it (see Session 10):** the user's actual preference, stated in
their very next message, was simpler than what this session built — they wanted the preview to
always fill the column's width with height just following (never height-bound/narrower-than-column),
not "fit within both dimensions." Session 10 replaced `fit()` with a plain width-driven model again.
This section is kept for the bug diagnosis (still correct: the root cause really was a fixed
`max_height` ceiling) but the `fit(avail_width, avail_height)` API described above no longer exists
in the code.

## Session 10 (2026-09-12): corrected sizing to width-driven (per explicit user preference) + added a resizable column sash

User clarified two things after session 9: (1) "maximize the video to column width, the height
should follow" — i.e. always fill the column's width, don't shrink narrower to respect a height
budget (rejecting session 9's dual-dimension `fit()`); (2) add a way to resize the left/right
columns against each other, with the left (video) column larger by default.

**(1) Fix (`gui/widgets/mpv_embed.py`):** removed `fit()`/`_last_bounds` entirely, restored a
simple width-driven model — `_refit(width)` sets `height = int(width * self._aspect)` with **no
cap of any kind**, wired back to a self-bound `<Configure>` (`_on_configure`) since the widget is
gridded `sticky="ew"` again and tracks its column's width automatically. `set_aspect()` calls
`self._refit(self.winfo_width())`. Constructor no longer takes a `max_height` parameter at all —
there is nothing left to cap. This is simpler than session 9's approach and matches exactly what
the user asked for; the tradeoff (accepted implicitly by the user's request) is that an unusually
tall/portrait video in a wide column could in principle grow taller than the left pane's visible
area, since there's no longer any height ceiling — not observed in testing, not raised by the user.

**(2) Implemented (`gui/panels/cut.py`):** replaced the fixed 50:50 grid-column split with a
`tk.PanedWindow(orient="horizontal", sashwidth=6, ...)` holding `left` and `right` as draggable
panes — see the layout section above for the `CTkScrollableFrame`/`_parent_frame` gotcha hit while
wiring this up. Left pane defaults wider (`width=560` initial) since the user prefers a larger video
column; `stretch="always"` on both panes so extra space from window resizing keeps distributing
rather than pinning the sash at a fixed pixel offset.

**Verified headlessly** via a real Tk mainloop: confirmed aspect stays exact (no cap, no
pillarboxing) across window resizes (960×680 -> 529×297; maximized 1600×1000 -> 822×462) and across
a simulated sash drag on a 1600×900 window (`paned.sash_place`): widened left pane 822×462 ->
928×522, narrowed to 400×225 — width and height moved together in every case, matching the video's
aspect exactly. **Not yet confirmed by the user with a real mouse drag on the sash or a real loaded
video.**

## Session 11 (2026-09-12): made the left pane's controls scrollable + Start/End transport buttons and keybindings

User confirmed session 10's fixes work, then asked for two more things: (1) make both columns
scrollable when their content overflows; (2) add a button + keybinding to seek to the start (Home)
and end (End) of the video.

**(1) `right` was already a `CTkScrollableFrame`** — no change needed there. **`left` could not
simply become one**, per the standing architecture constraint (Bug 2 / the class docstring): a
foreign HWND (`MpvEmbed`) can't live inside a `CTkScrollableFrame`'s Canvas. **Fix
(`gui/panels/cut.py`):** split `left` into two stacked children — `left_top` (fixed, non-scrolling:
header, video dropdown, `MpvEmbed`) and `left_scroll` (a `CTkScrollableFrame` below it: transport
buttons, Set Start/End, hint label), with `left.grid_rowconfigure(1, weight=1)` so `left_scroll`
claims whatever vertical room `left_top` doesn't use and scrolls once its own content exceeds that.
This is the same "fixed region + scrollable region below it" pattern from session 2's bug 4 fix,
reapplied at one level deeper (inside the left pane rather than inside the whole panel).
**Verified headlessly:** confirmed via direct widget introspection (not just a screenshot) that at
a real achievable window height in this environment (~749px, capped by a 768px virtual display —
not a code issue), `left_scroll`'s canvas had `bbox("all")` content height 98px but only ~28px of
actually visible height, i.e. it was genuinely scrolling, not just present-but-empty.

**(2) Implemented (`gui/widgets/mpv_embed.py`):** added `seek_start()` (`["seek", 0,
"absolute+exact"]` then `["set_property", "pause", False]` — resumes playback too, matching the
"play from start" framing) and `seek_end()` (`["seek", 100, "absolute-percent+exact"]` — asks mpv
for the end directly via percentage, no need to know the video's actual duration here). Bound
`<Home>`/`<End>` on `MpvEmbed.surface` the same way as the existing seek keys (same-process Tk
focus, not the never-confirmed cross-process OS focus). **Implemented (`gui/panels/cut.py`):**
added "⏮ Start" and "End ⏭" buttons at the two ends of the transport button row, and updated the
keybinding hint label to mention "Home/End = start/end". **Verified headlessly:** simulated
`event_generate("<Home>")`/`("<End>")` on the surface widget confirmed no exceptions; `seek_start`/
`seek_end` also confirmed to no-op safely when mpv isn't running. **Not confirmed against a real
mpv process** — check next session that Home/End and the two new buttons actually move playback to
the first/last frame.

## Session 12 (2026-09-12): enabled mpv's native OSC seekbar

User asked to "enable mpv native seeker" — mpv's own on-screen-controller progress bar
(click-drag to scrub), as an alternative to the custom transport buttons/keybindings built in
sessions 6-11. **Key realization:** mouse events don't have the cross-process keyboard-focus
problem that blocked `_focus_mpv`'s `SetFocus`/`AttachThreadInput` approach — Win32 routes mouse
messages by hit-testing screen position, not by which window has input focus, so clicks/drags on
mpv's embedded child HWND reach mpv directly regardless of whether it ever gets real OS focus.
The OSC was already on by default (mpv's `--osc` default is `yes`), just never deliberately
enabled/verified in this embedding.

**Fix (`gui/widgets/mpv_embed.py` `load()`):** added `--osc=yes` (explicit) and
`--script-opts=osc-visibility=always` (the OSC's visibility is a script-opt of `osc.lua`, not a
top-level CLI flag — `--osc-visibility` alone fails with "option not found", confirmed via
`mpv.exe --list-options`). `always` instead of the default `auto` (which hides the bar after
mouse-idle) keeps it discoverable in a small embedded preview.

**Verified for real**, not just headless: wrote a throwaway driver (`gui/_test_osc.py`, deleted
after) that embeds mpv in a real Tk window loaded with a generated sample video, moves the OS
cursor over the window via `SetCursorPos`, and screenshots with PIL `ImageGrab`. Screenshot showed
the OSC bar rendered and visible (position "00:00:03 / 00:00:10 (39%)", play/pause + prev/next
buttons, draggable progress bar) — confirms the native seeker renders in the embedded window.
Actual mouse-drag scrubbing wasn't simulated (no synthetic-drag test), so **still needs a real
user click-drag test** to confirm the seek itself lands correctly, but rendering + the focus-free
mouse-routing reasoning both check out.

**Follow-up same session: removed the filename mpv/osc.lua drew on top of the video.** Turning on
`osc-visibility=always` surfaced two separate filename labels that only ever showed on hover before
(and so went unnoticed): a top-left overlay and a small label in the bottom control bar. Root-caused
via `strings bin/mpv.exe` (osc.lua is compiled into the binary, not a loose file, so this was the
only way to inspect its option names) — this mpv build's osc.lua has **two independent title
options**, not one:

- `windowcontrols_title` (default `"${media-title}"`) — drawn as part of osc.lua's own
  "window controls" bar, which activates automatically because `--border=no` leaves the embedded
  window with no native OS title bar for it to fall back to. This was the top-left overlay.
- `title` (also `"${media-title}"` by default) — a separate label the bottom `bottombar` layout
  draws next to its transport buttons.

**Fix (`gui/widgets/mpv_embed.py`):** added `osc-windowcontrols=no` (also drops the useless
minimize/maximize/close buttons osc.lua would otherwise draw — meaningless for a borderless embed)
and `osc-title=` (blank) to the `--script-opts=` list. Verified via the same real-embed-window
screenshot technique: both labels gone, only the time/percentage OSD (from the pre-existing
`--osd-level=3`) and the seekbar remain.

## Open / unresolved — READ THIS FIRST NEXT SESSION

- **Session 11's scrollable left pane and Start/End controls are unconfirmed by the user** — check
  with a real video and a genuinely short window that the left pane's controls become reachable via
  scrolling, and that Home/End (keys and buttons) actually jump to the first/last frame.
- **Session 10's width-driven resize + draggable column sash is unconfirmed by the user** — check
  with a real video that maximizing fills the column width with no black bars, and that dragging the
  sash between panes actually works with the mouse (only `sash_place()`-simulated in this
  environment, not a real drag).
- The aspect-ratio fix (`set_aspect`) is untested against a real video/ffprobe — confirm the
  `csv=s=x:p=0` parsing produces sane `width`/`height` and black bars are gone; also confirm the
  fallback-to-9/16 path when ffprobe can't read dimensions.
- The second-range Set Start/End fix (`segment_row_list.py`) is logically sound and headless-
  verified but not yet clicked through by the user with two-or-more ranges.
- End<Start ordering has no validation anywhere — still unconfirmed/untouched whether this matters
  to the user.
- None of the plan's other manual verification steps (process cleanup on video-switch,
  panel-switch-away/back, app-close) have been confirmed yet.
- The original two-column 50:50 split and log-console collapse were confirmed OK by the user before
  session 10 replaced the fixed split with a draggable `PanedWindow` — the *content* of each pane
  is unchanged, only how their widths are determined, so this earlier confirmation should still
  mostly hold, but the resize mechanism itself is new/unconfirmed (see the item above).

## Change log

- 2026-09-12 (sessions 1-12): built the embedded mpv preview end-to-end and iterated through
  seek-accuracy, resize/pillarboxing, scrollable-pane, and native-OSC fixes. Full narrative is in
  the numbered session sections above (each already stands alone); this entry replaces the earlier
  per-session change-log list, which had grown to duplicate them (was dominating this file per the
  project's memory-compaction rule). Condensed 2026-09-12 ~10:30.
- 2026-10-14 15:20: Replaced the left-pane Set Start/Set End buttons with a ⏺ button beside each Start/End entry in the range rows (same pattern as the Overlay panel). `SegmentRowList` got an optional `on_capture(idx, is_start)`; when set, rows are compact (entries 92px, ✕ instead of Delete, no Select button, focusing a field selects the row, selected row gets a blue border). Cut's pane widths now 400/345 and transport buttons 48px. Trim's use of SegmentRowList is unchanged. Headless-verified only.
- 2026-10-14 15:26: Row delete is now a ghost ✕ (new `widgets/delete_control.py`: `make_delete_button`, `confirm_delete`) at the far right of each range row, red only on hover, with a native Yes/No dialog (default No). Rows still at their creation values (or empty) delete without a dialog. Same in Overlay (`OverlayPanel.request_delete`) and Trim (shared `SegmentRowList`). Headless-verified with mocked dialog; real dialog click UNCONFIRMED.
- 2026-10-14 15:57: The Cut left pane (video dropdown, MpvEmbed, transport buttons, hint) is no longer built in `panels/cut.py` — it moved to the shared `widgets/video_pane.py` (`VideoPane`), also used by Trim and Overlay. `CutPanel` still exposes `self.video_menu` / `self.mpv_embed` from it. Docstring in `cut.py` about the left pane layout still applies, now to `VideoPane`. Trim got the same layout ([[trim-panel-redesign]]).
