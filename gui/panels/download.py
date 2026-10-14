import threading
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.download import Downloader, fetch_formats

if TYPE_CHECKING:
    from app import App

_BEST_LABEL = "Best available"


class DownloadPanel(ctk.CTkFrame):
    def __init__(self, parent, app: "App"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.downloader = Downloader()
        self._running = False
        self._quality_options = [{"label": _BEST_LABEL, "height": None}]
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text="Download", font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        ctk.CTkLabel(self, text="YouTube URLs (one per line, for bulk download)").grid(
            row=1, column=0, padx=16, pady=(4, 0), sticky="w"
        )
        self.url_box = ctk.CTkTextbox(self, height=90)
        self.url_box.grid(row=2, column=0, padx=16, pady=(2, 8), sticky="ew")

        quality_row = ctk.CTkFrame(self, fg_color="transparent")
        quality_row.grid(row=3, column=0, padx=16, pady=(0, 4), sticky="ew")
        quality_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(quality_row, text="Quality:").grid(row=0, column=0, padx=(0, 8), sticky="w")
        self.quality_menu = ctk.CTkOptionMenu(quality_row, values=[_BEST_LABEL])
        self.quality_menu.grid(row=0, column=1, sticky="ew")

        self.fetch_btn = ctk.CTkButton(
            quality_row, text="Fetch Info", width=100, command=self._fetch_info
        )
        self.fetch_btn.grid(row=0, column=2, padx=(8, 0))

        self.info_label = ctk.CTkLabel(
            self, text="Quality/size are probed from the first URL and applied to the whole batch.",
            text_color="#999",
        )
        self.info_label.grid(row=4, column=0, padx=16, sticky="w")

        ctk.CTkLabel(
            self, text="Saves to project folder as: <video title>.mp4", text_color="#999"
        ).grid(row=5, column=0, padx=16, pady=(4, 8), sticky="w")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=6, column=0, padx=16, pady=8, sticky="w")
        self.run_btn = ctk.CTkButton(btn_frame, text="Download", command=self._run)
        self.run_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = ctk.CTkButton(btn_frame, text="Stop", command=self._stop, state="disabled")
        self.stop_btn.pack(side="left")

    def _urls(self) -> list[str]:
        text = self.url_box.get("1.0", "end")
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _fetch_info(self):
        urls = self._urls()
        if not urls:
            self.app.log("[Download] Enter at least one URL first.")
            return

        self.fetch_btn.configure(state="disabled")
        first_url = urls[0]

        def worker():
            title, options = fetch_formats(first_url, log=self.app.log)

            def apply():
                self.fetch_btn.configure(state="normal")
                self._quality_options = [{"label": _BEST_LABEL, "height": None}] + options
                labels = [o["label"] for o in self._quality_options]
                self.quality_menu.configure(values=labels)
                self.quality_menu.set(labels[0])
                if title:
                    suffix = " (applies to whole batch)" if len(urls) > 1 else ""
                    self.info_label.configure(text=f"Probed: {title}{suffix}")

            self.app.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def _selected_height(self):
        label = self.quality_menu.get()
        for opt in self._quality_options:
            if opt["label"] == label:
                return opt["height"]
        return None

    def _run(self):
        if self._running:
            return

        if not self.app.ensure_project_dir():
            return

        urls = self._urls()
        if not urls:
            self.app.log("[Download] Please enter at least one YouTube URL.")
            return

        project_dir = self.app.project.project_dir
        height = self._selected_height()

        self._running = True
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        def worker():
            try:
                self.downloader.download_bulk(project_dir, urls, height=height, log=self.app.log)
            finally:
                self.app.log_result("[Download] Finished", project_dir)
                self._running = False
                self.app.after(0, self._on_finished)

        threading.Thread(target=worker, daemon=True).start()

    def _stop(self):
        self.stop_btn.configure(state="disabled")
        self.downloader.stop()

    def _on_finished(self):
        self.run_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
