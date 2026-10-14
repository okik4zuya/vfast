import os
import threading
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.media import list_videos, format_duration
from core.trim import trim_video, bulk_trim
from core.cut import parse_time
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


class TrimPanel(ctk.CTkFrame):
    """Same two-pane layout as CutPanel: embedded mpv preview on the left (`VideoPane`, which
    explains why it stays off any scrolling container), controls on the right. Times are taken from
    the player with the ⏺ buttons beside Start/End instead of typing them or using a separate mpv."""

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
        paned = tk.PanedWindow(self, orient="horizontal", sashwidth=6, sashrelief="raised",
                               bd=0, bg=self.winfo_toplevel().cget("bg"))
        paned.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)

        pane = VideoPane(paned, self._on_video_change,
                         hint="⏺ beside Start/End takes the player's current time.")
        paned.add(pane, minsize=260, width=400, stretch="always")
        self.video_menu = pane.video_menu
        self.mpv_embed = pane.mpv_embed

        right = ctk.CTkScrollableFrame(paned, fg_color="transparent")
        right.grid_columnconfigure(0, weight=1)
        # PanedWindow.add() needs a direct child: the scrollable frame's real parent wrapper.
        paned.add(right._parent_frame, minsize=220, width=345, stretch="always")

        ctk.CTkLabel(right, text="Trim", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 8))

        self.timeline = Timeline(right, mode="single", on_change=self._on_timeline_change)
        self.timeline.grid(row=1, column=0, pady=(0, 6), sticky="ew")

        fields = ctk.CTkFrame(right, fg_color="transparent")
        fields.grid(row=2, column=0, sticky="w")
        self.start_entry = self._time_row(fields, 0, "Start", True)
        self.end_entry = self._time_row(fields, 1, "End", False)

        speed_frame = ctk.CTkFrame(right, fg_color="transparent")
        speed_frame.grid(row=3, column=0, pady=(8, 0), sticky="w")
        ctk.CTkLabel(speed_frame, text="Build speed:").pack(side="left", padx=(0, 10))
        self.speed_var = ctk.StringVar(value="balanced")
        for label, val in (("Fast", "fast"), ("Balanced", "balanced"), ("High", "high")):
            ctk.CTkRadioButton(speed_frame, text=label, variable=self.speed_var, value=val,
                               width=20).pack(side="left", padx=(0, 10))

        output_frame = ctk.CTkFrame(right, fg_color="transparent")
        output_frame.grid(row=4, column=0, pady=(8, 4), sticky="ew")
        output_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(output_frame, text="Output:").grid(row=0, column=0, sticky="w")
        self.output_entry = ctk.CTkEntry(output_frame)
        self.output_entry.grid(row=0, column=1, padx=8, sticky="ew")

        ctk.CTkButton(right, text="Run Trim", command=self._run_single).grid(
            row=5, column=0, sticky="e", pady=(4, 0))

        # --- Bulk trim ---
        ctk.CTkLabel(right, text="Bulk Trim (multiple clips)", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=6, column=0, pady=(20, 4), sticky="w")
        self.segment_list = SegmentRowList(right, on_capture=self._capture_row)
        self.segment_list.grid(row=7, column=0, sticky="ew")
        ctk.CTkButton(right, text="Run Bulk Trim", command=self._run_bulk).grid(
            row=8, column=0, pady=(8, 4), sticky="e")

    def _time_row(self, parent, row: int, label: str, is_start: bool) -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label, width=40, anchor="w").grid(row=row, column=0, pady=2)
        entry = ctk.CTkEntry(parent, width=120)
        entry.insert(0, "00:00:00.000")
        entry.grid(row=row, column=1, padx=(0, 4), pady=2)
        entry.bind("<FocusOut>", lambda e: self._on_field_change())
        entry.bind("<Return>", lambda e: self._on_field_change())
        ctk.CTkButton(parent, text="⏺", width=28,
                      command=lambda: self._capture_single(is_start)).grid(row=row, column=2, pady=2)
        return entry

    # ---- video ----
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
        self.timeline.set_range(0.0, duration)
        self.start_entry.delete(0, "end")
        self.start_entry.insert(0, format_duration(0.0))
        self.end_entry.delete(0, "end")
        self.end_entry.insert(0, format_duration(duration))
        self.output_entry.delete(0, "end")
        if media:
            base, ext = os.path.splitext(media.name)
            self.output_entry.insert(0, f"trimmed_{base}{ext}")
            self.mpv_embed.set_aspect(media.width, media.height)
            try:
                self.mpv_embed.load(media.path)
            except OSError as e:
                self.app.log(f"[Trim] Failed to start mpv preview: {e}")
        else:
            self.mpv_embed.stop()

    # ---- time capture ----
    def _capture(self, apply):
        """Read the mpv position off the Tk thread, then apply(seconds) on it."""
        if not self.mpv_embed.is_running():
            self.app.log("[Trim] mpv preview is not running.")
            return

        def on_result(seconds):
            if seconds is None:
                self.app.log("[Trim] Could not read mpv position — try again.")
                return
            apply(seconds)

        self.mpv_embed.get_time_pos_async(on_result)

    def _capture_single(self, is_start: bool):
        entry = self.start_entry if is_start else self.end_entry

        def apply(seconds):
            entry.delete(0, "end")
            entry.insert(0, format_duration(seconds))
            self._on_field_change()

        self._capture(apply)

    def _capture_row(self, idx: int, is_start: bool):
        def apply(seconds):
            start, end = self.segment_list.get_segments()[idx]
            s = format_duration(seconds)
            self.segment_list.set_row(idx, s if is_start else start, end if is_start else s)

        self._capture(apply)

    # ---- sync ----
    def _on_timeline_change(self, idx, start, end):
        self.start_entry.delete(0, "end")
        self.start_entry.insert(0, format_duration(start))
        self.end_entry.delete(0, "end")
        self.end_entry.insert(0, format_duration(end))

    def _on_field_change(self):
        try:
            start = parse_time(self.start_entry.get())
            end = parse_time(self.end_entry.get())
        except ValueError:
            return
        if end > start:
            self.timeline.set_range(start, end)

    # ---- run ----
    def _run_single(self):
        if self._running:
            return
        if not self.app.ensure_project_dir():
            return
        media = self._current_video()
        if not media:
            self.app.log("[Trim] No video selected.")
            return

        start = self.start_entry.get().strip()
        end = self.end_entry.get().strip()
        output_name = self.output_entry.get().strip()
        if not output_name:
            self.app.log("[Trim] Output filename required.")
            return
        output_path = os.path.join(self.app.project.project_dir, output_name)
        preset, crf = _SPEED_TIERS[self.speed_var.get()]

        self._running = True

        def worker():
            try:
                ok = trim_video(media.path, start, end, output_path, log=self.app.log,
                                preset=preset, crf=crf)
                if ok:
                    self.app.log_result(f"[Trim] Done: {os.path.basename(output_path)}", output_path)
            finally:
                self._running = False

        threading.Thread(target=worker, daemon=True).start()

    def _run_bulk(self):
        if self._running:
            return
        if not self.app.ensure_project_dir():
            return
        media = self._current_video()
        if not media:
            self.app.log("[Trim] No video selected.")
            return

        segments = self.segment_list.get_segments()
        if not segments:
            self.app.log("[Trim] Add at least one segment row.")
            return

        preset, crf = _SPEED_TIERS[self.speed_var.get()]
        output_dir = self.app.project.project_dir
        self._running = True

        def worker():
            try:
                count = bulk_trim(media.path, segments, output_dir, is_video=True, log=self.app.log,
                                  preset=preset, crf=crf)
                if count > 0:
                    self.app.log_result(f"[Trim] Created {count} clip(s)", output_dir)
            finally:
                self._running = False

        threading.Thread(target=worker, daemon=True).start()
