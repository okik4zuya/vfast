import os
import threading
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.media import list_videos, format_duration
from core.audio import remove_audio

if TYPE_CHECKING:
    from app import App


class RemoveAudioPanel(ctk.CTkFrame):
    def __init__(self, parent, app: "App"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._running = False
        self.videos = []
        self._build()
        self._refresh_files()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Remove Audio", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=16, pady=(16, 8), sticky="w"
        )

        ctk.CTkLabel(self, text="Video:").grid(row=1, column=0, padx=16, sticky="w")
        self.video_menu = ctk.CTkOptionMenu(self, values=["(no videos found)"], command=lambda _: self._on_change())
        self.video_menu.grid(row=1, column=1, padx=16, sticky="ew", pady=4)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=2, column=0, columnspan=2, padx=16, pady=(16, 16), sticky="ew")
        bottom.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bottom, text="Output filename:").grid(row=0, column=0, sticky="w")
        self.output_entry = ctk.CTkEntry(bottom)
        self.output_entry.grid(row=0, column=1, padx=8, sticky="ew")

        self.run_btn = ctk.CTkButton(bottom, text="Run Remove Audio", command=self._run)
        self.run_btn.grid(row=0, column=2, padx=(8, 0))

    def _refresh_files(self):
        project_dir = self.app.project.project_dir
        self.videos = list_videos(project_dir) if project_dir else []
        self.video_menu.configure(values=[v.name for v in self.videos] or ["(no videos found)"])
        self.video_menu.set(self.videos[0].name if self.videos else "(no videos found)")
        self._on_change()

    def _current_video(self):
        name = self.video_menu.get()
        return next((v for v in self.videos if v.name == name), None)

    def _on_change(self):
        media = self._current_video()
        if media:
            base, ext = os.path.splitext(media.name)
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, f"{base}_noaudio{ext}")

    def _run(self):
        if self._running:
            return
        if not self.app.ensure_project_dir():
            return

        video = self._current_video()
        if not video:
            self.app.log("[RemoveAudio] No video selected.")
            return

        output_name = self.output_entry.get().strip()
        if not output_name:
            self.app.log("[RemoveAudio] Output filename required.")
            return
        output_path = os.path.join(self.app.project.project_dir, output_name)

        self._running = True
        self.run_btn.configure(state="disabled")

        def worker():
            try:
                ok = remove_audio(video.path, output_path, log=self.app.log)
                if ok:
                    self.app.log_result(f"[RemoveAudio] Done: {os.path.basename(output_path)}", output_path)
            finally:
                self._running = False
                self.app.after(0, lambda: self.run_btn.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()
