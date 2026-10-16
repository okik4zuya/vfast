import os
import threading
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk

from core import segspec, settings
from core import spec as specmod
from core.media import list_videos, format_duration
from core.trim import trim_video, bulk_trim
from core.cut import parse_time
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


class TrimPanel(ctk.CTkFrame):
    """Same two-pane layout as CutPanel: embedded mpv preview on the left (`VideoPane`, which
    explains why it stays off any scrolling container), controls on the right. Times are taken from
    the player with the ⏺ buttons beside Start/End instead of typing them or using a separate mpv."""

    def __init__(self, parent, app: "App"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._running = False
        self.videos = []
        self.session = new_session(self, segspec.TrimSession)
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

        head = ctk.CTkFrame(right, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(head, text="Trim", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        spec_menu(head, self._save_spec, self._load_spec, self._reset_spec).pack(side="right")

        self.banner = SpecBanner(right, on_keep=self._keep_spec)
        self.banner.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self.banner.grid_remove()

        self.timeline = Timeline(right, mode="single", on_change=self._on_timeline_change)
        self.timeline.grid(row=2, column=0, pady=(0, 6), sticky="ew")

        fields = ctk.CTkFrame(right, fg_color="transparent")
        fields.grid(row=3, column=0, sticky="w")
        self.start_entry = self._time_row(fields, 0, "Start", True)
        self.end_entry = self._time_row(fields, 1, "End", False)

        speed_frame = ctk.CTkFrame(right, fg_color="transparent")
        speed_frame.grid(row=4, column=0, pady=(8, 0), sticky="w")
        ctk.CTkLabel(speed_frame, text="Build speed:").pack(side="left", padx=(0, 10))
        saved = settings.get("trim_quality", "balanced")
        self.speed_var = ctk.StringVar(value=saved if saved in _SPEED_TIERS else "balanced")
        self.speed_var.trace_add("write", lambda *_: settings.set("trim_quality", self.speed_var.get()))
        for label, val in (("Fast", "fast"), ("Balanced", "balanced"), ("High", "high")):
            ctk.CTkRadioButton(speed_frame, text=label, variable=self.speed_var, value=val,
                               width=20).pack(side="left", padx=(0, 10))

        output_frame = ctk.CTkFrame(right, fg_color="transparent")
        output_frame.grid(row=5, column=0, pady=(8, 4), sticky="ew")
        output_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(output_frame, text="Output:").grid(row=0, column=0, sticky="w")
        self.output_entry = ctk.CTkEntry(output_frame)
        self.output_entry.grid(row=0, column=1, padx=8, sticky="ew")

        ctk.CTkButton(right, text="Run Trim", command=self._run_single).grid(
            row=6, column=0, sticky="e", pady=(4, 0))

        # --- Bulk trim ---
        ctk.CTkLabel(right, text="Bulk Trim (multiple clips)", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=7, column=0, pady=(20, 4), sticky="w")
        self.segment_list = SegmentRowList(right, on_capture=self._capture_row, on_change=self._persist)
        self.segment_list.grid(row=8, column=0, sticky="ew")
        ctk.CTkButton(right, text="Run Bulk Trim", command=self._run_bulk).grid(
            row=9, column=0, pady=(8, 4), sticky="e")

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
            self._sync_widgets(duration)
        if media:
            fp = specmod.fingerprint(media.path, media.duration, media.width, media.height)
            if fp:
                self.session.apply_probe(self.session.generation, fp)
        self._show_issues()
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

    # ---- spec (<video>.trim.json) ----
    def _duration(self) -> float:
        """Duration of the spec's video (not the dropdown's: while switching, widgets still hold the old one)."""
        media = next((v for v in self.videos if v.path == self.session.video), None)
        return media.duration if media else 0.0

    @staticmethod
    def _set_entry(entry, text: str):
        entry.delete(0, "end")
        entry.insert(0, text)

    def _sync_widgets(self, duration: float):
        """spec -> widgets. Call inside `session.applying()` so nothing writes back.
        An empty start/end in the spec means 'whole video', so it follows whichever video is loaded."""
        spec = self.session.spec
        self._set_entry(self.start_entry, spec["start"] or format_duration(0.0))
        self._set_entry(self.end_entry, spec["end"] or format_duration(duration))
        try:
            start, end = parse_time(self.start_entry.get()), parse_time(self.end_entry.get())
        except ValueError:
            start, end = 0.0, duration
        if end > start:
            self.timeline.set_range(start, end)
        else:
            self.timeline.set_range(0.0, duration)
        self.segment_list.clear()
        for s, e in spec["bulk"]:
            self.segment_list.add_row(s, e)
            if not s and not e:  # add_row would leave an empty pair as is, but keep it explicit
                self.segment_list.set_row(len(self.segment_list.rows) - 1, "", "")

    def _persist(self):
        """widgets -> spec. Start at 0 / end at the video's end are stored as "" (= whole video)."""
        if self.session.video is None:
            return
        try:
            start = self.start_entry.get().strip()
            end = self.end_entry.get().strip()
            bulk = [list(r) for r in self.segment_list.get_segments()]
        except tk.TclError:
            return  # widgets already gone
        dur = self._duration()
        try:
            if parse_time(start) == 0.0:
                start = ""
        except ValueError:
            pass
        try:
            if dur > 0 and abs(parse_time(end) - dur) < 0.002:
                end = ""
        except ValueError:
            pass
        self.session.update(start=start, end=end, bulk=bulk)
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
            self._sync_widgets(self._duration())
        self._show_issues()

    def _save_spec(self):
        media = self._current_video()
        if not media:
            self.app.log("[Trim] No video selected.")
            return
        self._persist()
        path = self.session.default_export_path()  # always next to the video, named after it
        try:
            self.session.export_to(path)
            self.app.log(f"[Trim] Spec saved: {path}")
        except OSError as e:
            self.app.log(f"[Trim] Could not save spec: {e}")

    def _load_spec(self):
        media = self._current_video()
        if not media:
            self.app.log("[Trim] No video selected.")
            return
        path = ask_load_path(media.path, "Trim")
        if not path:
            return
        ok, warns = self.session.import_from(path)
        for w in warns:
            self.app.log(f"[Trim] {os.path.basename(path)}: {w}")
        if ok:
            with self.session.applying():
                self._sync_widgets(self._duration())
            self.app.log(f"[Trim] Spec loaded: {os.path.basename(path)}")
        self._show_issues()

    def destroy(self):
        # Navigation destroys the panel: persist what is typed (an entry may not have lost focus yet).
        try:
            self._persist()
            self.session.flush()
        except Exception:
            pass
        super().destroy()

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
            self._persist()  # set_row() doesn't notify

        self._capture(apply)

    # ---- sync ----
    def _on_timeline_change(self, idx, start, end):
        self.start_entry.delete(0, "end")
        self.start_entry.insert(0, format_duration(start))
        self.end_entry.delete(0, "end")
        self.end_entry.insert(0, format_duration(end))
        self._persist()

    def _on_field_change(self):
        self._persist()
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
