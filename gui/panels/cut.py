import os
import threading
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.media import list_videos, format_duration
from core.cut import cut_media, parse_time
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

        ctk.CTkLabel(right, text="Cut", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ctk.CTkLabel(right, text="Timeline:").grid(row=1, column=0, columnspan=2, sticky="w")
        self.timeline = Timeline(right, mode="multi", on_change=self._on_timeline_change)
        self.timeline.grid(row=2, column=0, columnspan=2, pady=(4, 8), sticky="ew")

        ctk.CTkLabel(right, text="Remove ranges:").grid(row=3, column=0, columnspan=2, sticky="w")
        self.segment_list = SegmentRowList(right, selectable=True,
                                            on_change=self._on_segments_change,
                                            on_select=self._on_segment_select,
                                            default_range=self._default_range,
                                            on_capture=self._apply_mpv_time)
        self.segment_list.grid(row=4, column=0, columnspan=2, sticky="ew")

        speed_frame = ctk.CTkFrame(right, fg_color="transparent")
        speed_frame.grid(row=5, column=0, columnspan=2, pady=(8, 0), sticky="w")
        ctk.CTkLabel(speed_frame, text="Build speed:").pack(side="left", padx=(0, 12))
        self.speed_var = ctk.StringVar(value="balanced")
        ctk.CTkRadioButton(speed_frame, text="Fast", variable=self.speed_var,
                           value="fast").pack(side="left", padx=(0, 12))
        ctk.CTkRadioButton(speed_frame, text="Balanced", variable=self.speed_var,
                           value="balanced").pack(side="left", padx=(0, 12))
        ctk.CTkRadioButton(speed_frame, text="High Quality", variable=self.speed_var,
                           value="high").pack(side="left")

        output_frame = ctk.CTkFrame(right, fg_color="transparent")
        output_frame.grid(row=6, column=0, columnspan=2, pady=(8, 4), sticky="ew")
        output_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(output_frame, text="Output filename:").grid(row=0, column=0, sticky="w")
        self.output_entry = ctk.CTkEntry(output_frame)
        self.output_entry.grid(row=0, column=1, padx=8, sticky="ew")

        run_btn = ctk.CTkButton(right, text="Run Cut", command=self._run)
        run_btn.grid(row=7, column=1, pady=(12, 4), sticky="e")

    def _refresh_files(self):
        project_dir = self.app.project.project_dir
        self.videos = list_videos(project_dir) if project_dir else []
        self.video_menu.configure(values=[v.name for v in self.videos] or ["(no videos found)"])
        self.video_menu.set(self.videos[0].name if self.videos else "(no videos found)")
        self._on_video_change()

    def _current_video(self):
        name = self.video_menu.get()
        return next((v for v in self.videos if v.name == name), None)

    def _on_video_change(self):
        media = self._current_video()
        duration = media.duration if media else 0.0
        self.timeline.set_duration(duration)
        if not self.segment_list.rows:
            self.segment_list.add_row(*self._default_range())
        self._on_segments_change()
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
        media = self._current_video()
        duration = media.duration if media else 0.0
        existing = [e for s, e in self._parsed_ranges() if e > 0]
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

    def _on_segment_select(self, idx: int):
        self.timeline.set_active(idx)

    def _on_timeline_change(self, idx, start, end):
        self.segment_list.set_row(idx, format_duration(start), format_duration(end))

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
