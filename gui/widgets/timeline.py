import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

BG = "#1a1a1a"
TRACK = "#3a3a3a"
KEPT = "#2563eb"
REMOVED = "#b91c1c"
ACTIVE_REMOVED = "#f97316"
HANDLE = "#f0f0f0"
HANDLE_ACTIVE = "#ffd43b"


class Timeline(ctk.CTkFrame):
    """Canvas-based range bar scaled to a known duration. No thumbnails.

    mode="single": one draggable start/end handle pair (Trim panel).
    mode="multi": every range renders as a shaded block; only the active
    range's handles are draggable (Cut panel); others are static.
    """

    HANDLE_RADIUS = 6
    TRACK_Y = 28
    HEIGHT = 56

    def __init__(self, parent, duration: float = 0.0, mode: str = "single",
                 on_change: Optional[Callable] = None):
        super().__init__(parent, fg_color="transparent")
        self.duration = max(duration, 0.001)
        self.mode = mode
        self.on_change = on_change

        self.ranges: list[list[float]] = []  # [start, end] per range
        self.active_index = 0

        self.canvas = tk.Canvas(self, height=self.HEIGHT, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="x", expand=True)
        self.canvas.bind("<Configure>", lambda e: self._redraw())
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        self._drag_target = None  # ("start"|"end", range_index)

    def set_duration(self, duration: float):
        self.duration = max(duration, 0.001)
        self._redraw()

    def set_range(self, start: float, end: float):
        self.ranges = [[start, end]]
        self.active_index = 0
        self._redraw()

    def get_range(self) -> tuple[float, float]:
        if not self.ranges:
            return (0.0, self.duration)
        s, e = self.ranges[0]
        return (s, e)

    def set_ranges(self, ranges: list[tuple[float, float]], active_index: int = 0):
        self.ranges = [[s, e] for s, e in ranges]
        self.active_index = active_index if ranges else 0
        self._redraw()

    def set_active(self, index: int):
        self.active_index = index
        self._redraw()

    def _x_of(self, t: float) -> int:
        w = max(self.canvas.winfo_width(), 1)
        pad = 10
        usable = max(w - 2 * pad, 1)
        return pad + int((t / self.duration) * usable)

    def _t_of(self, x: int) -> float:
        w = max(self.canvas.winfo_width(), 1)
        pad = 10
        usable = max(w - 2 * pad, 1)
        t = ((x - pad) / usable) * self.duration
        return max(0.0, min(self.duration, t))

    def _redraw(self):
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 1)
        y = self.TRACK_Y

        c.create_line(10, y, w - 10, y, fill=TRACK, width=4, capstyle="round")
        c.create_text(10, y + 16, text=_fmt(0), fill="#999", anchor="w", font=("Segoe UI", 8))
        c.create_text(w - 10, y + 16, text=_fmt(self.duration), fill="#999", anchor="e", font=("Segoe UI", 8))

        for i, (s, e) in enumerate(self.ranges):
            x1, x2 = self._x_of(s), self._x_of(e)
            active = (i == self.active_index)
            if self.mode == "multi":
                color = ACTIVE_REMOVED if active else REMOVED
                width = 8 if active else 6
            else:
                color, width = KEPT, 6
            c.create_line(x1, y, x2, y, fill=color, width=width, capstyle="round")

            handle_color = HANDLE_ACTIVE if active else HANDLE
            if self.mode == "single" or active:
                r = self.HANDLE_RADIUS
                c.create_oval(x1 - r, y - r, x1 + r, y + r, fill=handle_color, outline="")
                c.create_oval(x2 - r, y - r, x2 + r, y + r, fill=handle_color, outline="")

    def _on_press(self, event):
        if not self.ranges:
            return
        idx = self.active_index if self.mode == "multi" else 0
        if idx >= len(self.ranges):
            return
        s, e = self.ranges[idx]
        xs, xe = self._x_of(s), self._x_of(e)
        if abs(event.x - xs) <= self.HANDLE_RADIUS + 3:
            self._drag_target = ("start", idx)
        elif abs(event.x - xe) <= self.HANDLE_RADIUS + 3:
            self._drag_target = ("end", idx)
        else:
            self._drag_target = None

    def _on_drag(self, event):
        if not self._drag_target:
            return
        which, idx = self._drag_target
        t = self._t_of(event.x)
        s, e = self.ranges[idx]
        if which == "start":
            self.ranges[idx][0] = min(t, e - 0.05)
        else:
            self.ranges[idx][1] = max(t, s + 0.05)
        self._redraw()
        if self.on_change:
            self.on_change(idx, self.ranges[idx][0], self.ranges[idx][1])

    def _on_release(self, event):
        self._drag_target = None


def _fmt(seconds: float) -> str:
    seconds = max(0, int(seconds))
    mm, ss = divmod(seconds, 60)
    hh, mm = divmod(mm, 60)
    if hh:
        return f"{hh}:{mm:02d}:{ss:02d}"
    return f"{mm}:{ss:02d}"
