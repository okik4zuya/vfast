import datetime
import os
import threading
import time
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.screen_record import ScreenRecorder, list_microphones

if TYPE_CHECKING:
    from app import App


class ScreenRecordPanel(ctk.CTkFrame):
    def __init__(self, parent, app: "App"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.recorder = ScreenRecorder()
        self._start_time = None
        self._tick_job = None
        self._build()
        self._load_mics()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Screen Record", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=16, pady=(16, 8), sticky="w"
        )

        ctk.CTkLabel(self, text="Microphone:").grid(row=1, column=0, padx=16, sticky="w")
        self.mic_menu = ctk.CTkOptionMenu(self, values=["(loading...)"])
        self.mic_menu.grid(row=1, column=1, padx=16, sticky="ew", pady=4)

        ctk.CTkLabel(self, text="Capture:").grid(row=2, column=0, padx=16, sticky="w")
        capture_frame = ctk.CTkFrame(self, fg_color="transparent")
        capture_frame.grid(row=2, column=1, padx=16, sticky="w")
        self.capture_var = ctk.StringVar(value="full")
        ctk.CTkRadioButton(capture_frame, text="Full screen", variable=self.capture_var, value="full").pack(side="left", padx=(0, 12))
        ctk.CTkRadioButton(capture_frame, text="Region — not yet supported", variable=self.capture_var,
                           value="region", state="disabled").pack(side="left")

        ctk.CTkLabel(self, text="Output filename:").grid(row=3, column=0, padx=16, pady=(12, 4), sticky="w")
        self.output_entry = ctk.CTkEntry(self)
        self.output_entry.insert(0, self._default_filename())
        self.output_entry.grid(row=3, column=1, padx=16, pady=(12, 4), sticky="ew")

        self.status_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=16, weight="bold"))
        self.status_label.grid(row=4, column=0, columnspan=2, pady=(16, 8))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=5, column=0, columnspan=2, pady=(0, 16))
        self.start_btn = ctk.CTkButton(btn_frame, text="Start Recording", command=self._start)
        self.start_btn.pack(side="left", padx=8)
        self.stop_btn = ctk.CTkButton(btn_frame, text="Stop Recording", command=self._stop, state="disabled")
        self.stop_btn.pack(side="left", padx=8)

    def _default_filename(self) -> str:
        return f"recording_{datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')}.mp4"

    def _load_mics(self):
        def worker():
            mics = list_microphones()
            def apply():
                if mics:
                    self.mic_menu.configure(values=mics)
                    self.mic_menu.set(mics[0])
                else:
                    self.mic_menu.configure(values=["(no microphones found)"])
                    self.mic_menu.set("(no microphones found)")
            self.app.after(0, apply)
        threading.Thread(target=worker, daemon=True).start()

    def _start(self):
        if not self.app.ensure_project_dir():
            return
        mic = self.mic_menu.get()
        if not mic or mic.startswith("("):
            self.app.log("[ScreenRecord] No microphone selected.")
            return

        output_name = self.output_entry.get().strip() or self._default_filename()
        output_path = os.path.join(self.app.project.project_dir, output_name)
        self._last_output_path = output_path

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._start_time = time.monotonic()
        self._tick()

        threading.Thread(target=lambda: self.recorder.start(mic, output_path, log=self.app.log),
                         daemon=True).start()

    def _stop(self):
        self.stop_btn.configure(state="disabled")

        def worker():
            self.recorder.stop(log=self.app.log)
            if os.path.exists(self._last_output_path):
                self.app.log_result("[ScreenRecord] Saved", self._last_output_path)
            self.app.after(0, self._on_stopped)

        threading.Thread(target=worker, daemon=True).start()

    def _on_stopped(self):
        self.start_btn.configure(state="normal")
        if self._tick_job:
            self.after_cancel(self._tick_job)
            self._tick_job = None
        self.status_label.configure(text="")
        self.output_entry.delete(0, "end")
        self.output_entry.insert(0, self._default_filename())

    def _tick(self):
        if self._start_time is None:
            return
        elapsed = int(time.monotonic() - self._start_time)
        mm, ss = divmod(elapsed, 60)
        hh, mm = divmod(mm, 60)
        self.status_label.configure(text=f"● REC  {hh:02d}:{mm:02d}:{ss:02d}")
        self._tick_job = self.after(500, self._tick)
