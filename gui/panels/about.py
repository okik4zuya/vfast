import os
import subprocess
import sys
import threading
import webbrowser
from typing import TYPE_CHECKING

import customtkinter as ctk

from core import paths, settings
from core.version import APP_VERSION

if TYPE_CHECKING:
    from app import App

GITHUB_URL = "https://github.com/okik4zuya/vfast"

_FEATURES = [
    ("Merge", "Join several videos into one"),
    ("Speed", "Speed up / slow down a video"),
    ("Add / Remove / Extract Audio", "Replace, strip or pull out the audio track"),
    ("Denoise", "Reduce background noise (RNNoise)"),
    ("Trim / Cut", "Keep or remove time ranges with a live mpv preview"),
    ("Overlay", "Censor (box, blur, pixelate), text, logo and mute for a time range"),
    ("Screen Record", "Capture screen and microphone"),
    ("Download", "Fetch videos with yt-dlp"),
]

_SHORTCUTS = [
    ("Ctrl+B", "Collapse / expand the sidebar"),
    ("Space", "Play / pause (in a preview)"),
    ("← / →", "Seek 5 s (Shift: 1 s)"),
    ("Home / End", "Jump to start / end (in a preview)"),
]

_CREDITS = [
    ("FFmpeg", "video/audio processing engine (LGPL/GPL)"),
    ("mpv", "embedded preview player (GPL/LGPL)"),
    ("yt-dlp", "video downloading (Unlicense)"),
    ("RNNoise", "denoise model (BSD)"),
    ("CustomTkinter", "UI toolkit (MIT)"),
]


def _first_line(cmd: list[str]) -> str:
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
        return out.strip().splitlines()[0] if out.strip() else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "not found"


def _yt_dlp_version() -> str:
    try:
        from yt_dlp.version import __version__
        return __version__
    except Exception:
        return "not found"


class AboutPanel(ctk.CTkScrollableFrame):
    def __init__(self, parent, app: "App"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self._versions: dict[str, ctk.CTkLabel] = {}
        self._row = 0
        self._found: dict[str, str] = {}
        self._build()
        threading.Thread(target=self._load_versions, daemon=True).start()
        self._poll_versions()

    # -- layout helpers ---------------------------------------------------------------------
    def _heading(self, text: str):
        ctk.CTkLabel(self, text=text, font=ctk.CTkFont(size=15, weight="bold"), anchor="w").grid(
            row=self._row, column=0, padx=16, pady=(16, 4), sticky="w")
        self._row += 1

    def _table(self, rows: list[tuple[str, str]], key_width=190) -> dict[str, ctk.CTkLabel]:
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.grid(row=self._row, column=0, padx=16, sticky="ew")
        box.grid_columnconfigure(1, weight=1)
        self._row += 1
        values = {}
        for i, (k, v) in enumerate(rows):
            ctk.CTkLabel(box, text=k, width=key_width, anchor="w",
                         font=ctk.CTkFont(weight="bold")).grid(row=i, column=0, sticky="nw", pady=1)
            lbl = ctk.CTkLabel(box, text=v, anchor="w", justify="left", wraplength=520)
            lbl.grid(row=i, column=1, sticky="w", pady=1)
            values[k] = lbl
        return values

    # -- content ----------------------------------------------------------------------------
    def _build(self):
        ctk.CTkLabel(self, text="vfast", font=ctk.CTkFont(size=26, weight="bold"), anchor="w").grid(
            row=self._row, column=0, padx=16, pady=(16, 0), sticky="w")
        self._row += 1
        ctk.CTkLabel(
            self, anchor="w", justify="left", wraplength=640,
            text=f"Version {APP_VERSION}  ·  Windows video-processing toolkit.\n"
                 "A simple front-end for ffmpeg and mpv: pick a project folder, choose a tool, run.",
        ).grid(row=self._row, column=0, padx=16, sticky="w")
        self._row += 1

        link = ctk.CTkLabel(self, text=GITHUB_URL, anchor="w", cursor="hand2",
                            text_color=("#2563eb", "#60a5fa"))
        link.grid(row=self._row, column=0, padx=16, pady=(4, 0), sticky="w")
        link.bind("<Button-1>", lambda e: webbrowser.open(GITHUB_URL))
        self._row += 1

        self._heading("Tools")
        self._versions = self._table([("ffmpeg", "checking..."), ("mpv", "checking..."),
                                      ("yt-dlp", "checking...")])

        self._heading("What it does")
        self._table(_FEATURES)

        self._heading("Shortcuts")
        self._table(_SHORTCUTS)

        self._heading("This installation")
        self._table([
            ("Install folder", paths.get_tool_dir()),
            ("Bundled tools", paths.get_bin_dir()),
            ("Settings file", settings._path()),
            ("Project folder", self.app.project.project_dir or "(none selected)"),
            ("Python", sys.version.split()[0] + (" (frozen)" if getattr(sys, "frozen", False) else "")),
        ], key_width=140)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=self._row, column=0, padx=16, pady=(8, 0), sticky="w")
        self._row += 1
        ctk.CTkButton(buttons, text="Open install folder", width=140,
                      command=lambda: os.startfile(paths.get_tool_dir())).grid(row=0, column=0)
        ctk.CTkButton(buttons, text="Open settings folder", width=140,
                      command=lambda: os.startfile(os.path.dirname(settings._path()))
                      ).grid(row=0, column=1, padx=8)
        self.copy_btn = ctk.CTkButton(buttons, text="Copy diagnostics", width=140,
                                      command=self._copy_diagnostics)
        self.copy_btn.grid(row=0, column=2)
        ctk.CTkButton(buttons, text="GitHub", width=100,
                      command=lambda: webbrowser.open(GITHUB_URL)).grid(row=0, column=3, padx=(8, 0))

        self._heading("Built with")
        self._table(_CREDITS, key_width=140)

        ctk.CTkLabel(
            self, anchor="w", justify="left", wraplength=640, text_color="gray60",
            text="Bundled third-party tools keep their own licenses. vfast processes files locally; "
                 "it only uses the network when you use the Download panel.",
        ).grid(row=self._row, column=0, padx=16, pady=(12, 16), sticky="w")

    # -- runtime info -----------------------------------------------------------------------
    def _load_versions(self):
        # No Tk calls from this thread; _poll_versions on the Tk thread picks the result up.
        self._found = {
            "ffmpeg": _first_line([paths.ffmpeg_path(), "-version"]),
            "mpv": _first_line([paths.mpv_path(), "--version"]),
            "yt-dlp": _yt_dlp_version(),
        }

    def _poll_versions(self):
        if not self.winfo_exists():
            return  # user switched tabs before the probe finished
        if not self._found:
            self.after(100, self._poll_versions)
            return
        for name, text in self._found.items():
            self._versions[name].configure(text=text)

    def _copy_diagnostics(self):
        lines = [f"vfast {APP_VERSION}", GITHUB_URL, f"Python {sys.version.split()[0]}"]
        lines += [f"{k}: {v}" for k, v in self._found.items()]
        lines += [f"install: {paths.get_tool_dir()}", f"bin: {paths.get_bin_dir()}",
                  f"settings: {settings._path()}"]
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self.copy_btn.configure(text="Copied ✓")
        self.after(1500, lambda: self.copy_btn.configure(text="Copy diagnostics"))
