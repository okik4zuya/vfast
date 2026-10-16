"""Small shared UI pieces for panels that persist a per-video spec (core/sidecar.SpecSession)."""
import os
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

SPEC_LABEL = "Spec ▾"
_SAVE, _LOAD, _RESET = "Save spec", "Load spec...", "Reset spec"


class SpecBanner(ctk.CTkFrame):
    """Amber notice listing load warnings and problems of the saved spec against the selected video.
    Hidden when there is nothing to say. `on_keep` re-stamps the spec to the current file."""

    def __init__(self, parent, on_keep: Callable[[], None], wraplength: int = 300):
        super().__init__(parent, fg_color=("#fde68a", "#78350f"), corner_radius=6)
        self._on_keep = on_keep
        self.label = ctk.CTkLabel(self, text="", justify="left", anchor="w", wraplength=wraplength,
                                  text_color=("#451a03", "#fef3c7"))
        self.label.pack(fill="x", padx=8, pady=(6, 2))
        self.keep_btn = ctk.CTkButton(self, text="Keep spec", width=80, command=on_keep)
        self.keep_btn.pack(anchor="w", padx=8, pady=(0, 6))
        self.visible = False

    def show(self, messages: list[str], can_keep: bool) -> None:
        if not messages:
            self.visible = False
            self.grid_remove()
            return
        self.label.configure(text="\n".join("• " + m for m in messages))
        if can_keep:
            self.keep_btn.pack(anchor="w", padx=8, pady=(0, 6))
        else:
            self.keep_btn.pack_forget()
        self.visible = True
        self.grid()


def new_session(widget, session_cls):
    """A session whose debounce timers run on `widget`'s Tk event loop (cancel is safe after destroy)."""
    import tkinter as tk

    def cancel(handle):
        try:
            widget.after_cancel(handle)
        except tk.TclError:
            pass

    return session_cls(widget.after, cancel)


def spec_menu(parent, on_save: Callable[[], None], on_load: Callable[[], None],
              on_reset: Callable[[], None], width: int = 90) -> ctk.CTkOptionMenu:
    """The "Spec ▾" dropdown: Save spec... / Load spec... / Reset spec. Always shows its own label."""
    menu = ctk.CTkOptionMenu(parent, values=[_SAVE, _LOAD, _RESET], width=width)

    def choose(value: str):
        menu.set(SPEC_LABEL)
        {_SAVE: on_save, _LOAD: on_load, _RESET: on_reset}[value]()

    menu.configure(command=choose)
    menu.set(SPEC_LABEL)
    return menu


def ask_load_path(video: str, kind: str) -> str:
    return filedialog.askopenfilename(
        title=f"Load {kind} spec", initialdir=os.path.dirname(video),
        filetypes=[(f"{kind} spec", "*.json"), ("All files", "*.*")]) or ""
