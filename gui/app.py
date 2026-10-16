import os
import sys
import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog

import customtkinter as ctk


def _resource_path(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, relative)


@dataclass
class ProjectState:
    project_dir: str = ""


_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

_HEAVY_PANELS = ("cut", "trim", "overlay", "effects")  # embedded mpv: slow to build

_PANEL_CLASSES = {
    "merge": ("panels.merge", "MergePanel"),
    "speed": ("panels.speed", "SpeedPanel"),
    "add_audio": ("panels.add_audio", "AddAudioPanel"),
    "remove_audio": ("panels.remove_audio", "RemoveAudioPanel"),
    "extract_audio": ("panels.extract_audio", "ExtractAudioPanel"),
    "denoise": ("panels.denoise", "DenoisePanel"),
    "trim": ("panels.trim", "TrimPanel"),
    "cut": ("panels.cut", "CutPanel"),
    "overlay": ("panels.overlay", "OverlayPanel"),
    "effects": ("panels.effects", "EffectsPanel"),
    "screen_record": ("panels.screen_record", "ScreenRecordPanel"),
    "download": ("panels.download", "DownloadPanel"),
    "about": ("panels.about", "AboutPanel"),
}


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("vfast")
        self.geometry("960x680")
        self.minsize(760, 520)
        try:
            self.iconbitmap(_resource_path("assets/icon/app-icon.ico"))
        except Exception:
            pass

        self.project = ProjectState()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.selected_video = ""  # path of the video last picked in any panel; kept across panel switches
        self._nav_token = 0  # bumped per navigation so a slow, superseded panel load is discarded
        self._scan_progress = (0, 0)
        self._spin_job = None
        self._spin_i = 0

        self._build_layout()
        self._show_panel("merge")
        self.after(100, self._poll_queue)

    def _build_layout(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_topbar()

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew")
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)

        from sidebar import Sidebar
        self.sidebar = Sidebar(main, app=self)
        self.sidebar.grid(row=0, column=0, sticky="ns", padx=(8, 0), pady=8)

        content = ctk.CTkFrame(main, fg_color="transparent")
        content.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        content.grid_rowconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=0)
        content.grid_columnconfigure(0, weight=1)

        self.panel_frame = ctk.CTkFrame(content)
        self.panel_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
        self.panel_frame.grid_rowconfigure(0, weight=1)
        self.panel_frame.grid_columnconfigure(0, weight=1)

        # Loading overlay, shown (via place) over panel_frame while a panel's media is being scanned.
        self.loading = ctk.CTkFrame(self.panel_frame)
        self.loading_label = ctk.CTkLabel(self.loading, text="", font=ctk.CTkFont(size=15))
        self.loading_label.place(relx=0.5, rely=0.5, anchor="center")

        from log_console import LogConsole
        self.log_console = LogConsole(content, height=200)
        self.log_console.grid(row=1, column=0, sticky="ew")

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, height=48, corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(2, weight=1)

        ctk.CTkButton(bar, text="☰", width=36, command=self.toggle_sidebar).grid(
            row=0, column=0, padx=(10, 0), pady=10
        )
        # Ctrl+B like VS Code; skipped while typing, where Tk's own Ctrl+B (cursor left) applies.
        self.bind_all("<Control-b>", self._on_ctrl_b)

        ctk.CTkLabel(
            bar, text="vfast", font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=1, padx=14, pady=10)

        self.project_label = ctk.CTkLabel(bar, text="No project folder selected", anchor="w")
        self.project_label.grid(row=0, column=2, padx=8, pady=10, sticky="ew")

        ctk.CTkButton(bar, text="Open Folder", width=100, command=self._open_project_folder).grid(
            row=0, column=3, padx=(10, 0), pady=10
        )

        ctk.CTkButton(bar, text="Change", width=80, command=self._pick_project).grid(
            row=0, column=4, padx=10, pady=10
        )

        ctk.CTkButton(bar, text="Refresh", width=80, command=self.refresh_state).grid(
            row=0, column=5, padx=10, pady=10
        )

    def toggle_sidebar(self):
        self.sidebar.toggle()

    def _on_ctrl_b(self, event):
        if isinstance(self.focus_get(), (tk.Entry, tk.Text)):
            return
        self.toggle_sidebar()
        return "break"

    def _pick_project(self):
        path = filedialog.askdirectory(title="Select project folder")
        if path:
            self.set_project_dir(path)

    def _open_project_folder(self):
        if self.project.project_dir and os.path.isdir(self.project.project_dir):
            os.startfile(self.project.project_dir)

    def ensure_project_dir(self) -> bool:
        if self.project.project_dir and os.path.isdir(self.project.project_dir):
            return True
        self.log("[Info] No project folder selected. Please choose a folder.")
        path = filedialog.askdirectory(title="Select project folder")
        if path:
            self.set_project_dir(path)
            return True
        return False

    def preferred_video(self, videos) -> str:
        """Dropdown value for a freshly built panel: the video picked last, else the first one."""
        if not videos:
            return "(no videos found)"
        want = os.path.normcase(os.path.abspath(self.selected_video)) if self.selected_video else ""
        match = next((v for v in videos if os.path.normcase(os.path.abspath(v.path)) == want), None)
        return (match or videos[0]).name

    def set_project_dir(self, path: str):
        self.project.project_dir = path
        self.selected_video = ""  # a new folder starts with no remembered video
        self.project_label.configure(text=path)
        self.refresh_state()

    def refresh_state(self):
        # Re-show the active panel so it re-scans the (possibly new) project folder.
        if self.sidebar._active:
            self._show_panel(self.sidebar._active)

    def show_panel(self, name: str):
        self._show_panel(name)

    def _show_panel(self, name: str):
        if name not in _PANEL_CLASSES:
            return
        self._nav_token += 1
        token = self._nav_token
        # Immediate feedback: highlight the tab and drop the old panel now. Destroying first also
        # kills any embedded mpv, whose native window would otherwise paint over the overlay.
        self.sidebar.set_active(name)
        for w in self.panel_frame.winfo_children():
            if w is not self.loading:
                w.destroy()
        self._hide_loading()

        project_dir = self.project.project_dir
        if not (project_dir and os.path.isdir(project_dir)):
            self._build_panel(name)
            return

        # Panels call list_videos/list_audios synchronously in __init__; warm the probe cache off
        # the Tk thread first so those calls are instant and the UI (and spinner) stays alive.
        self._scan_progress = (0, 0)
        result = {"done": False}

        def progress(done, total):
            self._scan_progress = (done, total)

        def worker():
            from core.media import list_videos, list_audios
            try:
                list_videos(project_dir, progress)
                list_audios(project_dir)
            finally:
                result["done"] = True

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, lambda: self._show_loading_if_pending(token, result))
        self._wait_for_scan(token, name, result)

    def _wait_for_scan(self, token: int, name: str, result: dict):
        if token != self._nav_token:
            return
        if not result["done"]:
            self.after(30, lambda: self._wait_for_scan(token, name, result))
            return
        self._hide_loading()
        if name in _HEAVY_PANELS:
            # Widget construction + mpv launch run on the Tk thread (~1s) and cannot be threaded,
            # so paint a static message first; the spinner cannot animate during this part.
            self._show_overlay(f"{_SPINNER[0]}  Opening {name}...")
            self.update_idletasks()
        try:
            self._build_panel(name)
        finally:
            self._hide_loading()

    def _build_panel(self, name: str):
        import importlib
        module_name, class_name = _PANEL_CLASSES[name]
        panel_cls = getattr(importlib.import_module(module_name), class_name)
        panel = panel_cls(self.panel_frame, app=self)
        panel.grid(row=0, column=0, sticky="nsew")

    # -- loading overlay -------------------------------------------------------------------
    def _show_loading_if_pending(self, token: int, result: dict):
        # Delayed so a fully cached (instant) scan never flashes the overlay.
        if token != self._nav_token or result["done"]:
            return
        self._show_overlay("")
        self._spin()

    def _show_overlay(self, text: str):
        self.loading_label.configure(text=text)
        self.loading.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.loading.lift()
        self.configure(cursor="watch")

    def _spin(self):
        done, total = self._scan_progress
        frame = _SPINNER[self._spin_i % len(_SPINNER)]
        self._spin_i += 1
        detail = f" ({done}/{total})" if total else ""
        self.loading_label.configure(text=f"{frame}  Loading videos{detail}...")
        self._spin_job = self.after(80, self._spin)

    def _hide_loading(self):
        if self._spin_job is not None:
            self.after_cancel(self._spin_job)
            self._spin_job = None
        self.loading.place_forget()
        self.configure(cursor="")

    def log(self, text: str):
        self.log_queue.put(text)

    def log_result(self, message: str, path: str):
        self.log_queue.put(("result", message, path))

    def _poll_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                if isinstance(item, tuple):
                    self.log_console.write_result(*item[1:])
                else:
                    self.log_console.write(item)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)
