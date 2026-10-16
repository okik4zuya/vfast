import os
import threading
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk

from core import segspec, settings
from core import spec as specmod
from core.media import list_videos, format_duration
from core.cut import cut_media, parse_time
from widgets.spec_bar import SpecBanner, ask_load_path, new_session, spec_menu
from widgets.timeline import Timeline
from widgets.segment_row_list import SegmentRowList
from widgets.video_pane import VideoPane

if TYPE_CHECKING:
    from app import App

_SPEED_TIERS = {
    "fast": ("veryfast", 23),
    "balanced": ("fast", 18),
    "high": ("slow", 16),
}


class CutPanel(ctk.CTkFrame):
    """Two-pane layout, not a single CTkScrollableFrame: the embedded mpv
    preview is a real Win32 child window (SetParent via --wid), and nesting
    that inside a Canvas-backed scrollable container (as CTkScrollableFrame
    does) breaks the embed — the native window ends up invisible/detached
    from its intended position.

    The two panes live in a `tk.PanedWindow` with a draggable sash (not a
    plain grid split) so the user can resize the video vs. the controls —
    defaults to a larger left/video pane. `MpvEmbed` always fills the left
    pane's full width (`sticky="ew"`) with height simply derived from that
    width via the video's own aspect ratio (`mpv_embed.py`'s own
    `<Configure>` handler) — no height cap, so dragging the sash or
    maximizing the window grows/shrinks the preview correctly in both
    dimensions together instead of ever pillarboxing.

    Left pane (`left`): split into a fixed, non-scrolling `left_top` (header,
    video picker, `MpvEmbed` — the one region that must stay off the
    Canvas-backed scrolling path, since a foreign HWND can't live inside a
    `CTkScrollableFrame`'s Canvas) and a `CTkScrollableFrame` `left_scroll`
    below it (transport buttons, Set Start/End, keybinding hint) that takes
    whatever vertical room `left_top` doesn't use and scrolls once its own
    content overflows that.

    Right pane (`right`, scrollable): Timeline, ranges, speed, output, Run —
    gets the full panel height regardless of how tall the preview is."""

    def __init__(self, parent, app: "App"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._running = False
        self.videos = []
        self.session = new_session(self, segspec.CutSession)
        self._build()
        self._refresh_files()

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # PanedWindow, not a grid column split: gives the user a draggable
        # sash to resize video vs. controls. bg matches the real root window
        # background (queried at build time) since PanedWindow is a plain Tk
        # widget with no CTk theming of its own.
        paned = tk.PanedWindow(self, orient="horizontal", sashwidth=6, sashrelief="raised",
                                bd=0, bg=self.winfo_toplevel().cget("bg"))
        paned.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)

        # `stretch="always"`: the video pane keeps absorbing extra space when the window is resized,
        # rather than the sash staying pinned at a fixed pixel offset. `width=` only sets the
        # *initial* pane size; after that the user's drag (or window resize) decides it.
        pane = VideoPane(paned, self._on_video_change,
                         hint="⏺ beside Start/End takes the player's current time.")
        paned.add(pane, minsize=260, width=400, stretch="always")
        self.video_menu = pane.video_menu
        self.mpv_embed = pane.mpv_embed

        right = ctk.CTkScrollableFrame(paned, fg_color="transparent")
        right.grid_columnconfigure(1, weight=1)
        # CTkScrollableFrame's real Tk parent-relationship is one level down
        # (it draws itself on an internal canvas inside `_parent_frame`,
        # which is the actual direct child of `paned`) — PanedWindow.add()
        # requires a direct child, so add that wrapper, not `right` itself.
        paned.add(right._parent_frame, minsize=220, width=345, stretch="always")

        head = ctk.CTkFrame(right, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(head, text="Cut", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        spec_menu(head, self._save_spec, self._load_spec, self._reset_spec).pack(side="right")

        self.banner = SpecBanner(right, on_keep=self._keep_spec)
        self.banner.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.banner.grid_remove()

        ctk.CTkLabel(right, text="Timeline:").grid(row=2, column=0, columnspan=2, sticky="w")
        self.timeline = Timeline(right, mode="multi", on_change=self._on_timeline_change)
        self.timeline.grid(row=3, column=0, columnspan=2, pady=(4, 8), sticky="ew")

        ctk.CTkLabel(right, text="Remove ranges:").grid(row=4, column=0, columnspan=2, sticky="w")
        self.segment_list = SegmentRowList(right, selectable=True,
                                            on_change=self._on_segments_change,
                                            on_select=self._on_segment_select,
                                            default_range=self._default_range,
                                            on_capture=self._apply_mpv_time)
        self.segment_list.grid(row=5, column=0, columnspan=2, sticky="ew")

        speed_frame = ctk.CTkFrame(right, fg_color="transparent")
        speed_frame.grid(row=6, column=0, columnspan=2, pady=(8, 0), sticky="w")
        ctk.CTkLabel(speed_frame, text="Build speed:").pack(side="left", padx=(0, 12))
        saved = settings.get("cut_quality", "balanced")
        self.speed_var = ctk.StringVar(value=saved if saved in _SPEED_TIERS else "balanced")
        self.speed_var.trace_add("write", lambda *_: settings.set("cut_quality", self.speed_var.get()))
        ctk.CTkRadioButton(speed_frame, text="Fast", variable=self.speed_var,
                           value="fast").pack(side="left", padx=(0, 12))
        ctk.CTkRadioButton(speed_frame, text="Balanced", variable=self.speed_var,
                           value="balanced").pack(side="left", padx=(0, 12))
        ctk.CTkRadioButton(speed_frame, text="High Quality", variable=self.speed_var,
                           value="high").pack(side="left")

        output_frame = ctk.CTkFrame(right, fg_color="transparent")
        output_frame.grid(row=7, column=0, columnspan=2, pady=(8, 4), sticky="ew")
        output_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(output_frame, text="Output filename:").grid(row=0, column=0, sticky="w")
        self.output_entry = ctk.CTkEntry(output_frame)
        self.output_entry.grid(row=0, column=1, padx=8, sticky="ew")

        run_btn = ctk.CTkButton(right, text="Run Cut", command=self._run)
        run_btn.grid(row=8, column=1, pady=(12, 4), sticky="e")

    def _refresh_files(self):
        project_dir = self.app.project.project_dir
        self.videos = list_videos(project_dir) if project_dir else []
        self.video_menu.configure(values=[v.name for v in self.videos] or ["(no videos found)"])
        self.video_menu.set(self.app.preferred_video(self.videos))
        self._on_video_change()

    def _current_video(self):
        name = self.video_menu.get()
        media = next((v for v in self.videos if v.name == name), None)
        if media:
            self.app.selected_video = media.path  # survives switching panels
        return media

    def _on_video_change(self):
        self._persist()  # whatever is typed belongs to the video being left
        media = self._current_video()
        duration = media.duration if media else 0.0
        self.session.switch_video(media.path if media else None)
        self.timeline.set_duration(duration)
        with self.session.applying():
            self._sync_widgets()
        if media:
            fp = specmod.fingerprint(media.path, media.duration, media.width, media.height)
            if fp:
                self.session.apply_probe(self.session.generation, fp)
        self._show_issues()
        self.output_entry.delete(0, "end")
        if media:
            base, ext = os.path.splitext(media.name)
            self.output_entry.insert(0, f"{base}_cut{ext}")
            self.mpv_embed.set_aspect(media.width, media.height)
            try:
                self.mpv_embed.load(media.path)
            except OSError as e:
                self.app.log(f"[Cut] Failed to start mpv preview: {e}")
        else:
            self.mpv_embed.stop()

    def _default_range(self) -> tuple[str, str]:
        return self._range_after([e for s, e in self._parsed_ranges() if e > 0])

    def _range_after(self, existing: list[float]) -> tuple[str, str]:
        # The spec's video, not the dropdown's: while switching, rows still belong to the one being left.
        media = next((v for v in self.videos if v.path == self.session.video), None) or self._current_video()
        duration = media.duration if media else 0.0
        start = min(max(existing, default=0.0), duration)
        end = min(start + 5.0, duration)
        if end <= start:
            start = max(duration - 5.0, 0.0)
            end = duration
        return format_duration(start), format_duration(end)

    def _parsed_ranges(self):
        ranges = []
        for start, end in self.segment_list.get_segments():
            try:
                s, e = parse_time(start), parse_time(end)
            except ValueError:
                s, e = 0.0, 0.0
            ranges.append((s, e))
        return ranges

    def _on_segments_change(self):
        active = self.segment_list.selected_index or 0
        self.timeline.set_ranges(self._parsed_ranges(), active_index=active)
        self._persist()

    # ---- spec (<video>.cut.json) ----
    def _sync_widgets(self):
        """spec -> widgets. Call inside `session.applying()` so nothing writes back."""
        self.segment_list.clear()
        for start, end in self.session.spec["ranges"]:
            self.segment_list.add_row(start, end)
            if not start and not end:  # add_row would replace an empty pair by the default range
                self.segment_list.set_row(len(self.segment_list.rows) - 1, "", "")
        if not self.segment_list.rows:
            self.segment_list.add_row(*self._range_after([]))
        self._on_segments_change()

    def _persist(self):
        """widgets -> spec. A lone row still showing the default range is not worth saving."""
        if self.session.video is None:
            return
        try:
            rows = [list(r) for r in self.segment_list.get_segments()]
        except tk.TclError:
            return  # widgets already gone
        if rows == [list(self._range_after([]))]:
            rows = []
        self.session.update(ranges=rows)
        self.session.revalidate()
        self._show_issues()

    def _show_issues(self):
        s = self.session
        msgs = list(s.warnings) + [i.message for i in s.issues] + ([s.save_error] if s.save_error else [])
        self.banner.show(msgs, can_keep=any(i.kind in ("file_changed", "resolution_changed") for i in s.issues))

    def _keep_spec(self):
        self.session.accept_source()
        self._show_issues()

    def _reset_spec(self):
        self.session.reset()
        with self.session.applying():
            self._sync_widgets()
        self._show_issues()

    def _save_spec(self):
        media = self._current_video()
        if not media:
            self.app.log("[Cut] No video selected.")
            return
        self._persist()
        path = self.session.default_export_path()  # always next to the video, named after it
        try:
            self.session.export_to(path)
            self.app.log(f"[Cut] Spec saved: {path}")
        except OSError as e:
            self.app.log(f"[Cut] Could not save spec: {e}")

    def _load_spec(self):
        media = self._current_video()
        if not media:
            self.app.log("[Cut] No video selected.")
            return
        path = ask_load_path(media.path, "Cut")
        if not path:
            return
        ok, warns = self.session.import_from(path)
        for w in warns:
            self.app.log(f"[Cut] {os.path.basename(path)}: {w}")
        if ok:
            with self.session.applying():
                self._sync_widgets()
            self.app.log(f"[Cut] Spec loaded: {os.path.basename(path)}")
        self._show_issues()

    def destroy(self):
        # Navigation destroys the panel: persist what is typed (an entry may not have lost focus yet).
        try:
            self._persist()
            self.session.flush()
        except Exception:
            pass
        super().destroy()

    def _on_segment_select(self, idx: int):
        self.timeline.set_active(idx)

    def _on_timeline_change(self, idx, start, end):
        self.segment_list.set_row(idx, format_duration(start), format_duration(end))
        self._persist()

    def _apply_mpv_time(self, idx: int, is_start: bool):
        if not self.mpv_embed.is_running():
            self.app.log("[Cut] mpv preview is not running.")
            return

        def on_result(seconds):
            if seconds is None:
                self.app.log("[Cut] Could not read mpv position — try again.")
                return
            start_str, end_str = self.segment_list.get_segments()[idx]
            if is_start:
                start_str = format_duration(seconds)
            else:
                end_str = format_duration(seconds)
            self.segment_list.set_row(idx, start_str, end_str)
            self._on_segments_change()  # set_row() doesn't fire on_change itself

        self.mpv_embed.get_time_pos_async(on_result)

    def _run(self):
        if self._running:
            return
        if not self.app.ensure_project_dir():
            return
        media = self._current_video()
        if not media:
            self.app.log("[Cut] No video selected.")
            return

        segments = self.segment_list.get_segments()
        if not segments:
            self.app.log("[Cut] Add at least one range to remove.")
            return

        output_name = self.output_entry.get().strip()
        if not output_name:
            self.app.log("[Cut] Output filename required.")
            return
        output_path = os.path.join(self.app.project.project_dir, output_name)
        duration = media.duration
        preset, crf = _SPEED_TIERS[self.speed_var.get()]

        self._running = True

        def worker():
            try:
                ok = cut_media(media.path, segments, duration, output_path, is_video=True,
                                log=self.app.log, preset=preset, crf=crf)
                if ok:
                    self.app.log_result(f"[Cut] Done: {os.path.basename(output_path)}", output_path)
            finally:
                self._running = False

        threading.Thread(target=worker, daemon=True).start()
