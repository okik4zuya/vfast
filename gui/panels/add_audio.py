import os
import threading
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.media import list_videos, list_audios, format_duration
from core.audio import add_audio

if TYPE_CHECKING:
    from app import App


class AddAudioPanel(ctk.CTkFrame):
    def __init__(self, parent, app: "App"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._running = False
        self.videos = []
        self.audios = []
        self._build()
        self._refresh_files()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Add Audio", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=16, pady=(16, 8), sticky="w"
        )

        ctk.CTkLabel(self, text="Video:").grid(row=1, column=0, padx=16, sticky="w")
        self.video_menu = ctk.CTkOptionMenu(self, values=["(no videos found)"], command=lambda _: self._on_change())
        self.video_menu.grid(row=1, column=1, padx=16, sticky="ew", pady=4)

        ctk.CTkLabel(self, text="Audio:").grid(row=2, column=0, padx=16, sticky="w")
        self.audio_menu = ctk.CTkOptionMenu(self, values=["(no audio found)"], command=lambda _: self._on_change())
        self.audio_menu.grid(row=2, column=1, padx=16, sticky="ew", pady=4)

        mode_frame = ctk.CTkFrame(self, fg_color="transparent")
        mode_frame.grid(row=3, column=0, columnspan=2, padx=16, pady=(12, 4), sticky="w")
        self.mode_var = ctk.StringVar(value="replace")
        ctk.CTkRadioButton(mode_frame, text="Replace original audio", variable=self.mode_var,
                           value="replace", command=self._on_mode_change).pack(side="left", padx=(0, 12))
        ctk.CTkRadioButton(mode_frame, text="Mix with original", variable=self.mode_var,
                           value="mix", command=self._on_mode_change).pack(side="left")

        self.mix_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self.mix_frame, text="Mix volume (new track, 0.0-1.0):").pack(side="left")
        self.mix_volume_entry = ctk.CTkEntry(self.mix_frame, width=80)
        self.mix_volume_entry.insert(0, "0.30")
        self.mix_volume_entry.pack(side="left", padx=8)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=5, column=0, columnspan=2, padx=16, pady=(16, 16), sticky="ew")
        bottom.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bottom, text="Output filename:").grid(row=0, column=0, sticky="w")
        self.output_entry = ctk.CTkEntry(bottom)
        self.output_entry.grid(row=0, column=1, padx=8, sticky="ew")

        self.run_btn = ctk.CTkButton(bottom, text="Run Add Audio", command=self._run)
        self.run_btn.grid(row=0, column=2, padx=(8, 0))

        self._on_mode_change()

    def _on_mode_change(self):
        if self.mode_var.get() == "mix":
            self.mix_frame.grid(row=4, column=0, columnspan=2, padx=16, pady=(4, 4), sticky="w")
        else:
            self.mix_frame.grid_forget()

    def _refresh_files(self):
        project_dir = self.app.project.project_dir
        self.videos = list_videos(project_dir) if project_dir else []
        self.audios = list_audios(project_dir) if project_dir else []

        self.video_menu.configure(values=[v.name for v in self.videos] or ["(no videos found)"])
        self.video_menu.set(self.videos[0].name if self.videos else "(no videos found)")

        self.audio_menu.configure(values=[a.name for a in self.audios] or ["(no audio found)"])
        self.audio_menu.set(self.audios[0].name if self.audios else "(no audio found)")

        self._on_change()

    def _current_video(self):
        name = self.video_menu.get()
        return next((v for v in self.videos if v.name == name), None)

    def _current_audio(self):
        name = self.audio_menu.get()
        return next((a for a in self.audios if a.name == name), None)

    def _on_change(self):
        media = self._current_video()
        if media:
            base, ext = os.path.splitext(media.name)
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, f"{base}_with_audio{ext}")

    def _run(self):
        if self._running:
            return
        if not self.app.ensure_project_dir():
            return

        video = self._current_video()
        audio = self._current_audio()
        if not video or not audio:
            self.app.log("[AddAudio] Select both a video and an audio file.")
            return

        mix = self.mode_var.get() == "mix"
        try:
            mix_volume = float(self.mix_volume_entry.get().strip()) if mix else 0.3
        except ValueError:
            self.app.log("[AddAudio] Invalid mix volume.")
            return

        output_name = self.output_entry.get().strip()
        if not output_name:
            self.app.log("[AddAudio] Output filename required.")
            return
        output_path = os.path.join(self.app.project.project_dir, output_name)

        self._running = True
        self.run_btn.configure(state="disabled")

        def worker():
            try:
                ok = add_audio(video.path, audio.path, output_path, mix, mix_volume, log=self.app.log)
                if ok:
                    self.app.log_result(f"[AddAudio] Done: {os.path.basename(output_path)}", output_path)
            finally:
                self._running = False
                self.app.after(0, lambda: self.run_btn.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()
