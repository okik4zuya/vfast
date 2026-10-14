import tkinter as tk


class Tooltip:
    """Minimal hover tooltip. `enabled` is a callable so it can be switched off dynamically
    (the collapsed sidebar only needs tooltips while it is showing icons alone)."""

    def __init__(self, widget, text: str, enabled=lambda: True, delay: int = 400):
        self.widget, self.text, self.enabled, self.delay = widget, text, enabled, delay
        self._job = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._hide()
        if self.enabled():
            self._job = self.widget.after(self.delay, self._show)

    def _show(self):
        self._job = None
        if not self.enabled():
            return
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 6
        y = self.widget.winfo_rooty() + self.widget.winfo_height() // 2 - 12
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self._tip, text=self.text, bg="#2b2b2b", fg="#e5e5e5", relief="solid", bd=1,
                 padx=6, pady=2).pack()

    def _hide(self, _event=None):
        if self._job is not None:
            self.widget.after_cancel(self._job)
            self._job = None
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None
