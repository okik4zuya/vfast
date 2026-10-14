import os
import re
import subprocess

import customtkinter as ctk

from core import settings


_COLLAPSED_HEIGHT = 32
_ERROR_RE = re.compile(r"(?<![a-z])(error|failed|failure|traceback|gagal)(?![a-z])", re.I)


class LogConsole(ctk.CTkFrame):
    """Collapsible, collapsed by default so it never steals height from the panel above it (the
    video pane's controls used to be pushed off-screen). Collapsed, the header still shows the
    latest line plus a count of unread lines; a finished task (`write_result`) or an error line
    pops it open by itself. Only the user's own Hide/Show click is remembered across sessions —
    auto-expanding is transient. Logging works the same either way."""

    def __init__(self, parent, height=180):
        super().__init__(parent, height=height)
        self.expanded_height = height
        self._expanded = True
        self._unread = 0
        self.grid_propagate(False)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent", height=_COLLAPSED_HEIGHT)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        header.grid_propagate(False)
        ctk.CTkLabel(header, text="Log", anchor="w").grid(row=0, column=0, padx=(8, 4), sticky="w")
        self.preview = ctk.CTkLabel(header, text="", anchor="w", text_color="gray60")
        self.preview.grid(row=0, column=1, padx=4, sticky="ew")
        self.badge = ctk.CTkLabel(header, text="", text_color="#f59e0b",
                                  font=ctk.CTkFont(size=12, weight="bold"))
        self.badge.grid(row=0, column=2, padx=4)
        self.toggle_btn = ctk.CTkButton(header, text="▾ Hide", width=70, height=24,
                                         command=self._on_user_toggle)
        self.toggle_btn.grid(row=0, column=3, padx=4, pady=4, sticky="e")

        self.textbox = ctk.CTkTextbox(self, state="disabled", wrap="word")
        self.textbox.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        self._link_count = 0
        self.set_expanded(bool(settings.get("console_expanded", False)))

    def _on_user_toggle(self):
        self.toggle()
        settings.set("console_expanded", self._expanded)

    def toggle(self):
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool):
        self._expanded = expanded
        if expanded:
            self._unread = 0
            self._refresh_badge()
            self.preview.grid_remove()
            self.textbox.grid()
            self.configure(height=self.expanded_height)
            self.toggle_btn.configure(text="▾ Hide")
        else:
            self.textbox.grid_remove()
            self.preview.grid()
            self.configure(height=_COLLAPSED_HEIGHT)
            self.toggle_btn.configure(text="▸ Show")

    def _refresh_badge(self):
        self.badge.configure(text=f"● {self._unread}" if self._unread else "")

    def _note(self, text: str, force_open: bool):
        """Bookkeeping for a new line: collapsed-state preview + unread count, or auto-expand."""
        if self._expanded:
            return
        if force_open:
            self.set_expanded(True)
            return
        self._unread += 1
        self._refresh_badge()
        self.preview.configure(text=text.strip().splitlines()[-1] if text.strip() else "")

    def write(self, text: str):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", text + "\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")
        self._note(text, force_open=bool(_ERROR_RE.search(text)))

    def write_result(self, message: str, path: str):
        tag = f"link_{self._link_count}"
        self._link_count += 1

        self.textbox.configure(state="normal")
        self.textbox.insert("end", message + "  ")
        self.textbox.insert("end", path + "\n", tag)
        self.textbox.tag_config(tag, foreground="#38bdf8", underline=True)
        self.textbox.tag_bind(tag, "<Enter>", lambda e: self.textbox.configure(cursor="hand2"))
        self.textbox.tag_bind(tag, "<Leave>", lambda e: self.textbox.configure(cursor=""))
        self.textbox.tag_bind(tag, "<Button-1>", lambda e, p=path: self._reveal(p))
        self.textbox.see("end")
        self.textbox.configure(state="disabled")
        self._note(message, force_open=True)

    def _reveal(self, path: str):
        try:
            subprocess.run(["explorer", "/select,", os.path.normpath(path)])
        except Exception:
            pass

    def clear(self):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")
