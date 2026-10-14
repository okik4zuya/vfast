import threading
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.media import list_videos, list_audios, format_duration
from core.merge import merge_videos, merge_audios

if TYPE_CHECKING:
    from app import App


class MergePanel(ctk.CTkFrame):
    def __init__(self, parent, app: "App"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.mode = "videos"
        self._running = False
        self.row_widgets: list[dict] = []
        self._build()
        self._refresh_files()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Merge", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=16, pady=(16, 8), sticky="w"
        )

        mode_frame = ctk.CTkFrame(self, fg_color="transparent")
        mode_frame.grid(row=1, column=0, padx=16, sticky="w")
        self.mode_var = ctk.StringVar(value="videos")
        ctk.CTkRadioButton(mode_frame, text="Videos", variable=self.mode_var, value="videos",
                            command=self._on_mode_change).pack(side="left", padx=(0, 12))
        ctk.CTkRadioButton(mode_frame, text="Audio", variable=self.mode_var, value="audio",
                            command=self._on_mode_change).pack(side="left")

        self.list_frame = ctk.CTkScrollableFrame(self, height=260)
        self.list_frame.grid(row=2, column=0, padx=16, pady=8, sticky="nsew")
        self.list_frame.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(2, weight=1)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=3, column=0, padx=16, pady=(4, 16), sticky="ew")
        bottom.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bottom, text="Output filename:").grid(row=0, column=0, sticky="w")
        self.output_entry = ctk.CTkEntry(bottom)
        self.output_entry.insert(0, "merged_output.mp4")
        self.output_entry.grid(row=0, column=1, padx=8, sticky="ew")

        self.run_btn = ctk.CTkButton(bottom, text="Run Merge", command=self._run)
        self.run_btn.grid(row=0, column=2, padx=(8, 0))

    def _on_mode_change(self):
        self.mode = self.mode_var.get()
        ext = "merged_output.mp4" if self.mode == "videos" else "merged_output.mp3"
        self.output_entry.delete(0, "end")
        self.output_entry.insert(0, ext)
        self._refresh_files()

    def _refresh_files(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.row_widgets = []

        project_dir = self.app.project.project_dir
        if not project_dir:
            return

        files = list_videos(project_dir) if self.mode == "videos" else list_audios(project_dir)
        for i, media in enumerate(files):
            var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(self.list_frame, text="", variable=var, width=0,
                                  command=self._renumber)
            cb.grid(row=i, column=0, padx=(4, 4), pady=2)

            order_label = ctk.CTkLabel(self.list_frame, text="", width=24)
            order_label.grid(row=i, column=1, padx=(0, 4), pady=2, sticky="w")

            name_label = ctk.CTkLabel(self.list_frame, text=media.name, anchor="w")
            name_label.grid(row=i, column=2, padx=4, pady=2, sticky="ew")

            dur_label = ctk.CTkLabel(self.list_frame, text=format_duration(media.duration), width=110)
            dur_label.grid(row=i, column=3, padx=4, pady=2)

            up_btn = ctk.CTkButton(self.list_frame, text="▲", width=28, command=lambda j=i: self._move(j, -1))
            up_btn.grid(row=i, column=4, padx=(4, 0), pady=2)
            down_btn = ctk.CTkButton(self.list_frame, text="▼", width=28, command=lambda j=i: self._move(j, 1))
            down_btn.grid(row=i, column=5, padx=(2, 4), pady=2)

            self.row_widgets.append({
                "media": media, "var": var, "order_label": order_label,
                "name_label": name_label,
            })
        self._renumber()

    def _move(self, idx: int, delta: int):
        new_idx = idx + delta
        if new_idx < 0 or new_idx >= len(self.row_widgets):
            return
        self.row_widgets[idx], self.row_widgets[new_idx] = self.row_widgets[new_idx], self.row_widgets[idx]
        self._relayout()

    def _relayout(self):
        entries = self.row_widgets
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.row_widgets = []
        for entry in entries:
            media = entry["media"]
            var = entry["var"]
            i = len(self.row_widgets)
            cb = ctk.CTkCheckBox(self.list_frame, text="", variable=var, width=0,
                                  command=self._renumber)
            cb.grid(row=i, column=0, padx=(4, 4), pady=2)
            order_label = ctk.CTkLabel(self.list_frame, text="", width=24)
            order_label.grid(row=i, column=1, padx=(0, 4), pady=2, sticky="w")
            name_label = ctk.CTkLabel(self.list_frame, text=media.name, anchor="w")
            name_label.grid(row=i, column=2, padx=4, pady=2, sticky="ew")
            dur_label = ctk.CTkLabel(self.list_frame, text=format_duration(media.duration), width=110)
            dur_label.grid(row=i, column=3, padx=4, pady=2)
            up_btn = ctk.CTkButton(self.list_frame, text="▲", width=28, command=lambda j=i: self._move(j, -1))
            up_btn.grid(row=i, column=4, padx=(4, 0), pady=2)
            down_btn = ctk.CTkButton(self.list_frame, text="▼", width=28, command=lambda j=i: self._move(j, 1))
            down_btn.grid(row=i, column=5, padx=(2, 4), pady=2)
            self.row_widgets.append({
                "media": media, "var": var, "order_label": order_label,
                "name_label": name_label,
            })
        self._renumber()

    def _renumber(self):
        n = 0
        for entry in self.row_widgets:
            if entry["var"].get():
                n += 1
                entry["order_label"].configure(text=str(n))
            else:
                entry["order_label"].configure(text="")

    def _run(self):
        if self._running:
            return
        if not self.app.ensure_project_dir():
            return

        selected = [e["media"].path for e in self.row_widgets if e["var"].get()]
        if not selected:
            self.app.log("[Merge] No files selected.")
            return

        output_name = self.output_entry.get().strip()
        if not output_name:
            self.app.log("[Merge] Output filename required.")
            return

        import os
        output_path = os.path.join(self.app.project.project_dir, output_name)

        self._running = True
        self.run_btn.configure(state="disabled")

        mode = self.mode

        def worker():
            try:
                if mode == "videos":
                    ok = merge_videos(selected, output_path, log=self.app.log)
                else:
                    ok = merge_audios(selected, output_path, log=self.app.log)
                if ok:
                    self.app.log_result(f"[Merge] Done: {os.path.basename(output_path)}", output_path)
            finally:
                self._running = False
                self.app.after(0, lambda: self.run_btn.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()
