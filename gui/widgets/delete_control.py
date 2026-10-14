from tkinter import messagebox

import customtkinter as ctk

_MUTED = "gray55"


def make_delete_button(parent, command) -> ctk.CTkButton:
    """Deliberately low-key delete control: small, transparent, grey ✕ that only turns red on hover,
    so it is not clicked by accident next to frequently used buttons."""
    btn = ctk.CTkButton(parent, text="✕", width=22, height=22, fg_color="transparent",
                        hover_color="#b91c1c", text_color=_MUTED, border_width=0, command=command)
    btn.bind("<Enter>", lambda e: btn.configure(text_color="white"), add="+")
    btn.bind("<Leave>", lambda e: btn.configure(text_color=_MUTED), add="+")
    return btn


def confirm_delete(title: str, message: str, parent=None) -> bool:
    """Native Yes/No dialog, defaulting to No so a stray Enter does not delete."""
    return messagebox.askyesno(title, message, icon="warning", default="no", parent=parent)
