import customtkinter as ctk
from typing import TYPE_CHECKING

from core import settings
from widgets.tooltip import Tooltip

if TYPE_CHECKING:
    from app import App


STEPS = [
    ("merge", "Merge", "🔗"),
    ("speed", "Speed", "⏩"),
    ("add_audio", "Add Audio", "🎵"),
    ("remove_audio", "Remove Audio", "🔇"),
    ("extract_audio", "Extract Audio", "🎧"),
    ("denoise", "Denoise", "🌫"),
    ("trim", "Trim", "📏"),
    ("cut", "Cut", "✂"),
    ("overlay", "Overlay", "🔲"),
    ("effects", "Effects", "✨"),
    ("screen_record", "Screen Record", "⏺"),
    ("download", "Download", "⬇"),
    ("about", "About", "ℹ"),
]

_EXPANDED_W = 160
_COLLAPSED_W = 56


class Sidebar(ctk.CTkFrame):
    """Collapsible to an icon-only strip (labels become tooltips). No animation on purpose: the
    panel's embedded mpv is a native window that refits on every width change."""

    def __init__(self, parent, app: "App"):
        super().__init__(parent, width=_EXPANDED_W, corner_radius=8)
        self.app = app
        self.grid_propagate(False)
        self.buttons: dict[str, ctk.CTkButton] = {}
        self._labels: dict[str, tuple[str, str]] = {}
        self._active = ""
        self.collapsed = False
        self._build()
        self.set_collapsed(bool(settings.get("sidebar_collapsed", False)))

    def _build(self):
        self.grid_rowconfigure(len(STEPS), weight=1)
        for i, (name, label, icon) in enumerate(STEPS):
            btn = ctk.CTkButton(
                self,
                text=f"{icon}  {label}",
                width=_EXPANDED_W - 16,
                anchor="w",
                command=lambda n=name: self.app.show_panel(n),
            )
            btn.grid(row=i, column=0, padx=8, pady=(6 if i == 0 else 3, 3))  # tight: 13 buttons must fit minsize 520
            self.buttons[name] = btn
            self._labels[name] = (label, icon)
            Tooltip(btn, label, enabled=lambda: self.collapsed)

    def toggle(self):
        self.set_collapsed(not self.collapsed)
        settings.set("sidebar_collapsed", self.collapsed)

    def set_collapsed(self, collapsed: bool):
        self.collapsed = collapsed
        self.configure(width=_COLLAPSED_W if collapsed else _EXPANDED_W)
        for name, btn in self.buttons.items():
            label, icon = self._labels[name]
            if collapsed:
                btn.configure(text=icon, width=_COLLAPSED_W - 16, anchor="center",
                              font=ctk.CTkFont(size=18))
            else:
                btn.configure(text=f"{icon}  {label}", width=_EXPANDED_W - 16, anchor="w",
                              font=ctk.CTkFont())

    def set_active(self, name: str):
        self._active = name
        for n, btn in self.buttons.items():
            if n == name:
                btn.configure(fg_color=("#2563eb", "#1d4ed8"))
            else:
                btn.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])
