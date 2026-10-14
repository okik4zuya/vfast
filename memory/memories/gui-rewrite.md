---
name: gui-rewrite
description: customtkinter GUI replacement for vfast_v0.8.bat, implemented in gui/ — architecture, what was verified, what remains (PyInstaller/NSIS build)
metadata:
  type: project
  tier: T1
  created: 2026-09-11 11:40
  updated: 2026-10-14 15:57
---

# gui/ — customtkinter GUI rewrite

Implemented per an earlier session's implementation plan (not checked into the repo), mirroring `yt2s/gui/`'s
architecture (sidebar + panel host + shared log console + queue-based logging,
`threading.Thread` workers so ffmpeg/yt-dlp calls don't block the UI).

## Layout

- `gui/main.py`, `app.py`, `sidebar.py`, `log_console.py` — app shell, run via
  `venv-gui\Scripts\python.exe gui\main.py <project-folder>` from the repo root.
- `gui/core/*.py` — subprocess/business logic only, no UI imports, one module per operation
  (`paths`, `media`, `play`, `merge`, `speed`, `audio`, `trim`, `cut`, `screen_record`, `download`).
- `gui/panels/*.py` — one CTkFrame panel per menu item (merge, speed, add_audio, remove_audio,
  extract_audio, denoise, trim, cut, screen_record, download). Transcribe dropped per plan.
- `gui/widgets/segment_row_list.py`, `widgets/timeline.py` — reusable bulk-segment editor and
  Canvas range-bar timeline (no thumbnails), shared by trim (bulk mode) and cut panels.
- `gui/requirements.txt`, `vfast.spec`, `installer.nsi` — packaging (PyInstaller windowed exe +
  NSIS installer), not yet run end-to-end.

## Import convention (easy to get wrong)

`main.py` is run as `python gui/main.py` from the repo root, so Python sets `sys.path[0]` to
`gui/` itself (the script's directory) — **not** its parent. That means intra-`gui` modules import
as bare names (`from app import App`, `from sidebar import Sidebar`), and `core`/`panels`/`widgets`
import as top-level packages (`from core.paths import ...`) — there is no `gui.` prefix anywhere
inside `gui/`. This matches how `yt2s/main.py` does it one level up (run from `yt2s/` itself).

## Bug found and fixed during verification

`core/paths.py`'s `get_tool_dir()` originally went up only two directories from
`gui/core/paths.py`, landing on `gui/` instead of the repo root — `bin/ffmpeg.exe` resolved to
`gui/bin/ffmpeg.exe` (doesn't exist) instead of `vfast/bin/ffmpeg.exe`. Fixed to three `dirname()`
calls. Caught by actually running `core.screen_record.list_microphones()`, which shelled out and
hit `FileNotFoundError` — a smoke test that only builds panels (no subprocess calls) would have
missed this.

## Verified this session

- `venv-gui/` created (Python 3.13, customtkinter 5.2.2 + yt-dlp installed).
- All 9 panels build and `app.show_panel()` cleanly for each (headless smoke test).
- All core operations run for real against generated sample media (testsrc video + sine audio):
  merge videos, merge audios, speed change, add audio (replace + mix), remove audio, extract audio
  (copy + mp3), single trim, bulk trim, cut (both with-audio and no-audio input — the ported
  complement-cut filter_complex logic from `vfast_v0.8.bat:902-1124`).
- `list_microphones()` runs without crashing (returns `[]` in this sandbox, which has no dshow
  audio devices — untested against a real mic).

## Not yet done / verify next session

- No manual GUI interaction pass (dragging timeline handles, checking the segment row list UI,
  "Play in mpv" button) — only headless panel construction + core-function calls were verified.
- Screen recording Start/Stop never run against a real capture (no mic available in this sandbox).
- PyInstaller build (`pyinstaller gui/vfast.spec`) and NSIS installer (`makensis gui/installer.nsi`)
  never run — spec/script are written but unverified end-to-end, per plan step 2-3 of Verification.

## Download panel: two bugs found and fixed (2026-09-11)

Ran the Download panel for real against a live YouTube URL and hit `HTTP Error 403: Forbidden`.
Root-caused to two stacked issues in `gui/core/download.py`, both now fixed:

1. **Stale yt-dlp, resolved via ambient PATH — a latent fragility, not just a version bug.**
   `gui/core/download.py` calls bare `"yt-dlp"` (relies on subprocess PATH lookup) rather than an
   explicit interpreter/venv path. `gui/main.py` is documented as run via
   `venv-gui\Scripts\python.exe gui\main.py`, but running a venv's python.exe directly does **not**
   prepend that venv's `Scripts/` to PATH (only activating the venv does) — so the bare `"yt-dlp"`
   subprocess call resolves via system PATH instead. Checked with `where yt-dlp`: `venv-gui\Scripts`
   isn't on PATH at all; `venv\Scripts\yt-dlp.exe` resolves first (then a separate Python313
   user-level install). That's confirmed by the original failure log's version string
   (`2026.02.04`), which matches exactly what `venv/` had before this session's upgrade — not
   `venv-gui/`'s yt-dlp, which was already 2026.8.19 the whole time and was never actually being
   invoked. Fixed the immediate symptom with `pip install --upgrade yt-dlp` in `venv/` (→
   2026.8.19), but **the underlying fragility is unfixed**: `download.py` silently depends on
   whichever `yt-dlp.exe` happens to be first on system PATH, which is decoupled from which venv is
   "supposed" to run the GUI. Worth fixing properly (e.g. `sys.executable -m yt_dlp` or resolving
   the venv-gui path explicitly) rather than relying on PATH order — added to todo-list.
2. **Missing ffmpeg wiring (bigger, silent bug).** `download.py` invoked bare `"yt-dlp"` and never
   passed `--ffmpeg-location`, unlike every other ffmpeg-consuming module (`trim.py`, `merge.py`,
   `cut.py`, `audio.py`, `speed.py`, `screen_record.py`), all of which use
   `core.paths.ffmpeg_path()`. Since ffmpeg isn't on system PATH, yt-dlp's merge step silently
   no-oped — every download since this panel was written would have produced two orphaned files
   (video-only + audio-only) instead of one playable merged mp4, with only a warning line in the
   log, easy to miss. Fixed by importing `ffmpeg_path` and passing `--ffmpeg-location` in the
   `yt-dlp` command list, matching the convention everywhere else in `gui/core/`.

Verified end-to-end after both fixes: real download of a YouTube video → separate video+audio
streams → `[Merger] Merging formats into "....mp4"` → single correct output file, no leftovers.

## Download panel: bulk download, quality selection, stop (2026-09-11)

Extended `core/download.py` and `panels/download.py`:

- **Bulk**: URL entry is now a `CTkTextbox`, one URL per line; `Downloader.download_bulk()` runs
  them sequentially, logging `(i/n)` progress and a final success-count summary.
- **Quality + filesize**: `fetch_formats(url)` shells out to `yt-dlp -j` on the *first* URL in the
  batch, collects the best (by filesize) format per distinct height with a real vcodec, and returns
  labels like `1080p (~450 MB)`. Populates a `CTkOptionMenu` (plus a `Best available` default); the
  chosen height is applied to every URL in the batch via
  `format_selector(height)` → `bestvideo[height<=N][ext=mp4]+bestaudio[ext=m4a]/best[height<=N]`.
  One caveat: quality/size is only probed from the first URL, so a mixed-quality batch gets a
  single shared cap — acceptable for this tool's scope, but worth knowing if a batch spans videos
  with very different available resolutions.
- **Stop**: `Downloader` is now a class holding the live `Popen` handle; `stop()` sets a flag and
  `terminate()`s the current subprocess (mirrors `ScreenRecorder`'s start/stop pattern in
  `core/screen_record.py`). Halts both the current download and the remaining queue.
- **Also fixed while touching this file**: `_yt_dlp_cmd()` now calls
  `[sys.executable, "-m", "yt_dlp"]` instead of the bare `"yt-dlp"` string, closing the PATH-order
  fragility noted below (venv-gui's python no longer needs its own Scripts/ on PATH).

Verified for real: `fetch_formats()` against a live YouTube URL (returned 240p/144p with sizes),
and a full bulk download (1 URL, height-capped) end-to-end → single merged mp4 via
`Downloader.download_bulk()`. Stop button wasn't separately live-tested (terminate() on an
in-flight Popen) but follows the same pattern as the already-verified `ScreenRecorder.stop()`.

## inbox/ide.md debug items (2026-09-11)

Closed out 4 of 5 items from `inbox/ide.md` (see the implementation plan,
`debug-jadikan-videos-snazzy-newell.md`); item 5 (multi-video quality selection) needed no code
change — `format_selector(height)` already caps per-URL independently, only the "Fetch Info"
preview is limited to the first URL, left as-is per user decision.

1. **Default project folder**: `gui/main.py` now defaults to `~/Videos` (auto-created via
   `os.makedirs(exist_ok=True)`) when no argv is given, and `app.set_project_dir()` runs
   unconditionally on startup instead of only when an explicit path was passed.
2. **Open Folder button**: added to `app.py`'s topbar between the project label and "Change"
   (`os.startfile(project_dir)`).
3. **mpv OSD clock — two-step fix, first attempt incomplete.** Plan called for
   `--osd-fractions` alone (to get `HH:MM:SS.mmm` instead of `HH:MM:SS`). After implementing,
   user reported the clock wasn't showing *at all* in the top-left — `--osd-fractions` only
   changes the *format* of the OSD clock when mpv shows it (on seek/pause/etc.), it does not make
   it persistent. mpv's default `--osd-level=1` only flashes OSD on interaction. Fixed by also
   adding `--osd-level=3`, which keeps the statusline (time) permanently visible. Both flags now
   in `core/play.py`'s `play()`. **Lesson: when adding an mpv/ffmpeg CLI flag from
   documentation/memory, verify against the actual installed binary's real behavior/output rather
   than trusting the flag's name/description alone** — this is the second time in this file a fix
   needed correction after checking real tool output (see the dshow mic parsing entry below, and
   the original `get_tool_dir()` path bug).
4. **Screen record mic detection — plan's regex-based fix was itself wrong for the installed
   ffmpeg build.** Original bug: `list_microphones()` regex `r'"(.+Microphone.*)"'` only matched
   device names literally containing "Microphone". Plan's fix assumed dshow prints
   `"DirectShow video devices"` / `"DirectShow audio devices"` section headers (older ffmpeg
   behavior) — implemented that, but the user reported the mic *still* wasn't found. Checked
   `bin/ffmpeg.exe -list_devices true -f dshow -i dummy` output directly: this build (gyan.dev
   2025-09-15 git build) does **not** print those headers at all; each device line instead ends
   with a type suffix directly, e.g. `[dshow @ ...] "Microphone (Web Camera)" (audio)`, with
   `Alternative name "..."` sub-lines to skip. Rewrote `list_microphones()` to match
   `r'"(.+)"\s+\(audio\)\s*$'` per line instead of tracking a section state. Verified for real:
   `list_microphones()` now returns `['Microphone (Web Camera)']` against the actual bundled
   `bin/ffmpeg.exe`. **Whenever touching dshow/ffmpeg device-listing parsing in this repo, dump
   `bin/ffmpeg.exe -list_devices true -f dshow -i dummy` stderr directly first** — its output
   format is not stable across ffmpeg builds/versions, so don't trust a remembered or
   documented format.

## Denoise panel: added arnndn (RNNoise) method (2026-09-11)

`panels/denoise.py` had two methods (afftdn, anlmdn); added arnndn as a third. This ffmpeg build
(gyan.dev 2025-09-15) has **no embedded default model** for `arnndn` despite `-m`/`model` being
listed as an optional AVOption — confirmed by testing: `-af arnndn` (with or without `mix=`) fails
with "Error initializing filters" unless `-m <path>` is passed explicitly. Fixed by bundling a
general-purpose RNNoise model at `bin/models/rnnoise-general.rnnn` (299KB, from the public
rnnoise-models project) and adding `core.paths.rnnoise_model_path()`. `core/audio.py`'s
`denoise_audio()` now builds `arnndn=m='<path>':mix=<strength/100>` for this method — the
drive-letter colon in the Windows path must be escaped (`\:`) since ffmpeg's filter-option parser
treats `:` as the key=value separator; forward slashes avoid also needing to escape backslashes.
Verified end-to-end by calling `denoise_audio()` directly against generated sample media with the
real bundled `bin/ffmpeg.exe` — produced valid output. **Lesson (same pattern as the mpv OSD and
dshow mic fixes above): an ffmpeg filter's documented/AVOption-help behavior doesn't necessarily
match what a specific build actually does — verify by running the real binary.**

## Refresh button, task-completion reporting, Cut timeline fix, build-speed tiers (2026-09-12)

Implemented per `add-refresh-button-calm-lake.md`, four usability gaps:

1. **Topbar Refresh button** (`app.py`): calls existing `refresh_state()` — no new mechanism
   needed, it already destroys/recreates the active panel to rescan the project folder.
2. **Task-completion reporting**: `app.log_result(message, path)` pushes a `("result", msg, path)`
   tuple onto the existing log queue; `_poll_queue` branches on `isinstance(item, tuple)` to call
   `log_console.write_result()` instead of `write()`. `write_result` inserts the path under a
   per-call `link_N` tag (accent color + underline), binds hover cursor + click →
   `subprocess.run(["explorer", "/select,", path])` (wrapped in try/except, reveal not launch, per
   user's choice). Wired into every panel worker's success path (merge, speed, add/remove/extract
   audio, denoise, cut, trim single) and the special cases: bulk trim reports the output *dir* with
   a clip count, screen_record reports on Stop if the file exists, download reports the project dir
   (no single output path in bulk-URL mode).
3. **Cut timeline active-range visibility** (`widgets/timeline.py`): active remove-range now draws
   orange (`ACTIVE_REMOVED = "#f97316"`) at 8px vs. red 6px for inactive ranges, replacing the old
   behavior where every range was the same red and only the handle dots (invisible unless active)
   showed which one was selected.
4. **Build-speed tiers**: `cut_media`/`trim_video`/`bulk_trim` gained `preset`/`crf` params
   (Fast=veryfast/23, Balanced=fast/18 default, High Quality=slow/16), threaded through from a new
   radio-button trio in `panels/cut.py` and `panels/trim.py`. Software-only — no GPU/NVENC, per
   user's choice (no existing hardware-encoder detection in the codebase, not worth the platform
   risk).

**Output filename fields added afterward** (follow-up request, same session): Cut and Trim's
single-clip mode previously had no visible/editable output path — Cut hardcoded `cut_output.mp4`,
Trim silently derived `trimmed_<name><ext>`. Both now have an "Output filename" `CTkEntry`
(auto-populated per video-menu selection: `<name>_cut<ext>` for Cut, `trimmed_<name><ext>` for
Trim, matching the convention already used by merge/speed/audio panels), required before running.
Bulk Trim intentionally left alone — it produces multiple files via a `clip_N` naming pattern, not
a single output path.

Verified headlessly only (`app.show_panel()` for all 10 panels + isolated `LogConsole.write_result`
/ `Timeline._redraw` calls) — no manual GUI/mpv/ffmpeg pass done this session; still needs the
real-app checks listed in the plan's Verification section (drag timeline, run all 3 speed tiers
against real ffmpeg, click a result path to confirm Explorer opens).

## Cut panel: overflow past 5 remove-ranges hid the Run Cut button (2026-09-12)

User-reported bug: adding more than ~5 remove ranges in the Cut panel pushed "Run Cut" (and
everything below the segment list) out of the visible area, with no way to scroll to it —
`app.py`'s `panel_frame` hosts each panel as a plain fixed-size `CTkFrame`, so a panel's content
growing taller than the window just clips.

First attempt (wrong layer): made `widgets/segment_row_list.py`'s internal `rows_frame` a
`CTkScrollableFrame` instead of the panel itself. Screenshot showed a broken result — the inner
scrollable area rendered oversized and everything below it (Add range, speed tiers, output field,
Run Cut) vanished from layout entirely rather than just being scrolled past. **Lesson: nesting a
`CTkScrollableFrame` inside a panel that isn't itself scrollable/size-constrained produces broken
geometry, not graceful overflow — the scrollable container needs to be the outermost thing that's
allowed to overflow, not a bolted-on inner one.**

Fixed by reverting that and instead making `panels/cut.py`'s `CutPanel` itself subclass
`ctk.CTkScrollableFrame` (was `ctk.CTkFrame`) — the whole panel scrolls as one unit when its
content overflows the window.

Verified for real (not just headless): wrote a throwaway driver script
(`gui/_test_cut_overflow.py`, deleted after) that launches the real `App`, opens Cut, adds 8
ranges via `segment_list.add_row()`, and uses PIL `ImageGrab` to screenshot the live window.
Confirmed a scrollbar appears and, scrolled to bottom, "+ Add range", build speed, output
filename, and "Run Cut" are all present and clickable. First real GUI screenshot verification
done in this project (everything before this was headless `show_panel()` + core-function calls).

## Panel lifecycle (app.py) — relevant to any panel that owns a subprocess/resource

`App._show_panel(name)` (`app.py:115-141`) destroys every child of `panel_frame` via a plain
`for w in panel_frame.winfo_children(): w.destroy()` loop, then imports and constructs the new
panel class fresh. There is **no** `WM_DELETE_WINDOW` protocol registered anywhere in the app —
closing the window via the OS X button just lets Tk's own destroy cascade fire `<Destroy>` events
down the whole widget tree. Net effect: any widget that owns a live subprocess/handle (e.g. an
embedded player) must clean up via its own `<Destroy>` binding, not a custom `destroy()` override
or an app-level shutdown hook — `<Destroy>` is the one hook guaranteed to fire on every teardown
path (panel switch, app close, exception) with zero changes needed elsewhere. `refresh_state()`
also routes through `_show_panel`, so the "Refresh" topbar button and folder-change both destroy
and rebuild the active panel too, not just navigation.

## Cut panel architecture (as of 2026-09-12, before mpv-embed work — SUPERSEDED, see [[cut-panel-mpv-embed]])

`CutPanel` is no longer a `CTkScrollableFrame` itself — it was restructured again during the
mpv-embed work into a plain `CTkFrame` (fixed top area + nested `CTkScrollableFrame` body), because
embedding mpv's real Win32 window inside a `Canvas`-backed scrollable container doesn't work. Full
detail, plus two nasty Tk/CustomTkinter propagation bugs found along the way, in
[[cut-panel-mpv-embed]]. The collaborator descriptions below (Timeline, SegmentRowList, paths) are
still accurate; the `core/play.py` description is now Trim-only (Cut has its own `MpvEmbed` instead).

`panels/cut.py::CutPanel` (a `CTkScrollableFrame`, see overflow fix above) wires three collaborators:

- **`widgets/timeline.py::Timeline`** — pure `tk.Canvas` range bar, no video/thumbnails, no
  external deps. Time↔pixel math is `_x_of(t)`/`_t_of(x)` (10px padding each side). `mode="multi"`
  (Cut) draws every range as a shaded line, only the `active_index` range gets visible/draggable
  handle dots; `mode="single"` (Trim) always shows one draggable pair. Public API:
  `set_duration(d)`, `set_ranges(ranges, active_index)`, `set_active(i)`, `get_range()`. Drag
  handlers call `on_change(idx, start, end)` live during `<B1-Motion>`.
- **`widgets/segment_row_list.py::SegmentRowList`** — one row per remove-range, each a
  `CTkFrame` with index label + Start `CTkEntry` + End `CTkEntry` (+ optional per-row "Select"
  button when `selectable=True`, used only by Cut) + "Delete" button. Key gotcha:
  **`set_row(idx, start, end)` does NOT call `on_change`/`_notify_change()`** — callers that
  programmatically overwrite a row's text (e.g. `cut.py::_on_timeline_change`) must explicitly
  call whatever follow-up sync they need (`cut.py` calls `self._on_segments_change()` right after).
  `get_segments()` returns raw `(start_str, end_str)` tuples, unparsed. Shared verbatim by Trim's
  bulk mode (`selectable=False`) — don't add Cut-only buttons/params to this widget without
  checking Trim's usage.
- **`core/play.py::play(path, start=None)`** — fire-and-forget `subprocess.Popen([mpv_path(), path,
  "--osd-fractions", "--osd-level=3", ...])`, own top-level window, no IPC. Now used only by
  `trim.py`'s "▶ Play in mpv" button — Cut replaced this with an embedded `MpvEmbed` + IPC, see
  [[cut-panel-mpv-embed]].
- **`core/paths.py`** — `mpv_path()`/`ffmpeg_path()`/`ffprobe_path()` all resolve against
  `get_bin_dir()`, which branches on `sys.frozen` (dev: repo-root `bin/`; frozen: PyInstaller
  `_MEIPASS/bin`). Any new bundled binary/model follows this same pattern (see `rnnoise_model_path()`).

`CutPanel._on_video_change()` is the single place that re-syncs Timeline duration, seeds a default
segment row, and refreshes the output filename whenever the video dropdown changes or the panel is
freshly built — the natural hook point for anything that needs to react to "which video is loaded"
(confirmed as the hook used for the planned mpv-embed load/stop wiring, see
`in-gui-cut-panel-ancient-lerdorf.md` plan).

`gui/requirements.txt` has only `customtkinter==5.2.2` and `yt-dlp==2025.01.26` — no `pywin32`, no
image/video libs. Any feature needing e.g. Windows named-pipe IPC or frame decoding should default
to stdlib-only approaches unless a new dependency is explicitly justified.

## Change log

- 2026-09-11: Implemented gui/ per plan; verified all panels + core ops; fixed Download panel
  (stale yt-dlp, missing ffmpeg wiring) then extended it (bulk, quality/filesize, Stop); closed
  inbox/ide.md items 1-4 (project folder default, Open Folder button, mpv OSD clock, dshow mic
  parsing); added arnndn Denoise method with a bundled model. See sections above for detail.
  Recurring lesson: verify ffmpeg/mpv flag behavior against the real bundled binary, not docs.
- 2026-09-12: Added Refresh button, task-completion log reporting, Cut timeline active-range
  highlighting, build-speed tiers, and Output filename fields (Cut/Trim) — headless-verified only.
  Later same day: fixed Cut panel's >5-ranges overflow bug (Run Cut button unreachable) by making
  `CutPanel` a `CTkScrollableFrame`; verified with a real screenshot, not headless. See section
  above for the failed first attempt and why it broke.
- 2026-09-12 (later): Implemented embedded mpv preview in the Cut panel; restructured `CutPanel`
  off of `CTkScrollableFrame` again; found/fixed a `pack_propagate` vs `grid_propagate` bug and
  documented a `CTkFrame.bind()`-redirects-to-canvas landmine. Full detail in
  [[cut-panel-mpv-embed]] (dedicated file — this feature has enough non-obvious framework gotchas
  to warrant its own file rather than growing this one further).
- 2026-10-14 15:57: Panels/widgets added after the original rewrite: `panels/overlay.py` ([[overlay-engine]]), Trim and Cut rebuilt on embedded mpv, new widgets `video_pane.py`, `delete_control.py`, and `SegmentRowList(on_capture=)`. Sidebar now has 11 entries (Overlay added).
