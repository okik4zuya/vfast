import os
import threading
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.media import list_videos, format_duration
from core.speed import change_speed, is_valid_speed, MIN_SPEED, MAX_SPEED

if TYPE_CHECKING:
    from app import App


class SpeedPanel(ctk.CTkFrame):
    def __init__(self, parent, app: "App"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._running = False
        self.videos = []
        self._build()
        self._refresh_files()

    def _build(self):
        ctk.CTkLabel(self, text="Speed", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=16, pady=(16, 8), sticky="w"
        )

        ctk.CTkLabel(self, text="Video:").grid(row=1, column=0, padx=16, sticky="w")
        self.video_menu = ctk.CTkOptionMenu(self, values=["(no videos found)"], command=self._on_video_change)
        self.video_menu.grid(row=1, column=1, padx=16, sticky="ew", pady=4)
        self.grid_columnconfigure(1, weight=1)

        self.duration_label = ctk.CTkLabel(self, text="")
        self.duration_label.grid(row=2, column=1, padx=16, sticky="w")

        ctk.CTkLabel(self, text=f"Multiplier ({MIN_SPEED}-{MAX_SPEED}):").grid(row=3, column=0, padx=16, pady=(12, 4), sticky="w")
        self.mult_entry = ctk.CTkEntry(self)
        self.mult_entry.insert(0, "1.0")
        self.mult_entry.grid(row=3, column=1, padx=16, pady=(12, 4), sticky="w")
        self.mult_entry.bind("<KeyRelease>", lambda e: self._validate())

        self.error_label = ctk.CTkLabel(self, text="", text_color="#f87171")
        self.error_label.grid(row=4, column=1, padx=16, sticky="w")

        self.estimate_label = ctk.CTkLabel(self, text="Estimated output duration: —")
        self.estimate_label.grid(row=5, column=1, padx=16, sticky="w", pady=(4, 12))

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=6, column=0, columnspan=2, padx=16, pady=(0, 16), sticky="ew")
        bottom.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bottom, text="Output filename:").grid(row=0, column=0, sticky="w")
        self.output_entry = ctk.CTkEntry(bottom)
        self.output_entry.grid(row=0, column=1, padx=8, sticky="ew")

        self.run_btn = ctk.CTkButton(bottom, text="Run Speed Change", command=self._run)
        self.run_btn.grid(row=0, column=2, padx=(8, 0))

        self._validate()

    def _refresh_files(self):
        project_dir = self.app.project.project_dir
        self.videos = list_videos(project_dir) if project_dir else []
        if self.videos:
            self.video_menu.configure(values=[v.name for v in self.videos])
            self.video_menu.set(self.videos[0].name)
        else:
            self.video_menu.configure(values=["(no videos found)"])
            self.video_menu.set("(no videos found)")
        self._on_video_change(None)

    def _current_video(self):
        name = self.video_menu.get()
        for v in self.videos:
            if v.name == name:
                return v
        return None

    def _on_video_change(self, _):
        media = self._current_video()
        self.duration_label.configure(text=format_duration(media.duration) if media else "")
        self._update_output_name()
        self._validate()

    def _update_output_name(self):
        media = self._current_video()
        if not media:
            return
        mult = self.mult_entry.get().strip() or "1.0"
        base, ext = os.path.splitext(media.name)
        self.output_entry.delete(0, "end")
        self.output_entry.insert(0, f"{base}_{mult}x{ext}")

    def _validate(self):
        text = self.mult_entry.get().strip()
        try:
            mult = float(text)
        except ValueError:
            self.error_label.configure(text="Enter a numeric multiplier.")
            self.run_btn.configure(state="disabled")
            self.estimate_label.configure(text="Estimated output duration: —")
            return

        if not is_valid_speed(mult):
            self.error_label.configure(text=f"Multiplier must be between {MIN_SPEED} and {MAX_SPEED}.")
            self.run_btn.configure(state="disabled")
            self.estimate_label.configure(text="Estimated output duration: —")
            return

        self.error_label.configure(text="")
        self.run_btn.configure(state="normal")
        media = self._current_video()
        if media:
            self.estimate_label.configure(
                text=f"Estimated output duration: {format_duration(media.duration / mult)}"
            )
        self._update_output_name()

    def _run(self):
        if self._running:
            return
        if not self.app.ensure_project_dir():
            return

        media = self._current_video()
        if not media:
            self.app.log("[Speed] No video selected.")
            return

        try:
            mult = float(self.mult_entry.get().strip())
        except ValueError:
            return
        if not is_valid_speed(mult):
            return

        output_name = self.output_entry.get().strip()
        if not output_name:
            self.app.log("[Speed] Output filename required.")
            return
        output_path = os.path.join(self.app.project.project_dir, output_name)

        self._running = True
        self.run_btn.configure(state="disabled")

        def worker():
            try:
                ok = change_speed(media.path, mult, output_path, log=self.app.log)
                if ok:
                    self.app.log_result(f"[Speed] Done: {os.path.basename(output_path)}", output_path)
            finally:
                self._running = False
                self.app.after(0, lambda: self.run_btn.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()
