import os
import threading
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.media import list_videos, format_duration
from core.audio import denoise_audio

if TYPE_CHECKING:
    from app import App


class DenoisePanel(ctk.CTkFrame):
    def __init__(self, parent, app: "App"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._running = False
        self.videos = []
        self._build()
        self._refresh_files()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Denoise Audio", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=16, pady=(16, 8), sticky="w"
        )

        ctk.CTkLabel(self, text="Video:").grid(row=1, column=0, padx=16, sticky="w")
        self.video_menu = ctk.CTkOptionMenu(self, values=["(no videos found)"], command=lambda _: self._on_change())
        self.video_menu.grid(row=1, column=1, padx=16, sticky="ew", pady=4)

        mode_frame = ctk.CTkFrame(self, fg_color="transparent")
        mode_frame.grid(row=2, column=0, columnspan=2, padx=16, pady=(12, 4), sticky="w")
        self.method_var = ctk.StringVar(value="afftdn")
        ctk.CTkRadioButton(mode_frame, text="FFT denoise, general purpose", variable=self.method_var,
                           value="afftdn").pack(side="left", padx=(0, 12))
        ctk.CTkRadioButton(mode_frame, text="Non-local means, steady hiss/hum", variable=self.method_var,
                           value="anlmdn").pack(side="left", padx=(0, 12))
        ctk.CTkRadioButton(mode_frame, text="RNN denoise, best for speech/voice", variable=self.method_var,
                           value="arnndn").pack(side="left")

        strength_frame = ctk.CTkFrame(self, fg_color="transparent")
        strength_frame.grid(row=3, column=0, columnspan=2, padx=16, pady=(8, 4), sticky="ew")
        strength_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(strength_frame, text="Strength:").grid(row=0, column=0, sticky="w")
        self.strength_var = ctk.DoubleVar(value=25)
        self.strength_slider = ctk.CTkSlider(strength_frame, from_=1, to=100, variable=self.strength_var)
        self.strength_slider.grid(row=0, column=1, padx=8, sticky="ew")
        self.strength_label = ctk.CTkLabel(strength_frame, text="25")
        self.strength_label.grid(row=0, column=2, padx=(0, 8))
        self.strength_var.trace_add("write", lambda *_: self.strength_label.configure(
            text=str(int(self.strength_var.get()))
        ))

        self.highpass_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self, text="Also cut low-frequency rumble (highpass 100Hz)",
                        variable=self.highpass_var).grid(row=4, column=0, columnspan=2, padx=16, pady=(4, 4), sticky="w")

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=5, column=0, columnspan=2, padx=16, pady=(16, 16), sticky="ew")
        bottom.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bottom, text="Output filename:").grid(row=0, column=0, sticky="w")
        self.output_entry = ctk.CTkEntry(bottom)
        self.output_entry.grid(row=0, column=1, padx=8, sticky="ew")

        self.run_btn = ctk.CTkButton(bottom, text="Run Denoise", command=self._run)
        self.run_btn.grid(row=0, column=2, padx=(8, 0))

    def _refresh_files(self):
        project_dir = self.app.project.project_dir
        self.videos = list_videos(project_dir) if project_dir else []
        self.video_menu.configure(values=[v.name for v in self.videos] or ["(no videos found)"])
        self.video_menu.set(self.app.preferred_video(self.videos))
        self._on_change()

    def _current_video(self):
        name = self.video_menu.get()
        media = next((v for v in self.videos if v.name == name), None)
        if media:
            self.app.selected_video = media.path  # survives switching panels
        return media

    def _on_change(self):
        media = self._current_video()
        if media:
            base, ext = os.path.splitext(media.name)
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, f"{base}_denoised{ext}")

    def _run(self):
        if self._running:
            return
        if not self.app.ensure_project_dir():
            return

        video = self._current_video()
        if not video:
            self.app.log("[Denoise] No video selected.")
            return

        output_name = self.output_entry.get().strip()
        if not output_name:
            self.app.log("[Denoise] Output filename required.")
            return
        output_path = os.path.join(self.app.project.project_dir, output_name)
        method = self.method_var.get()
        strength = self.strength_var.get()
        highpass = self.highpass_var.get()

        self._running = True
        self.run_btn.configure(state="disabled")

        def worker():
            try:
                ok = denoise_audio(video.path, output_path, method, strength, highpass, log=self.app.log)
                if ok:
                    self.app.log_result(f"[Denoise] Done: {os.path.basename(output_path)}", output_path)
            finally:
                self._running = False
                self.app.after(0, lambda: self.run_btn.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()
