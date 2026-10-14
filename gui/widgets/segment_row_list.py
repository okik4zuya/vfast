from typing import Callable, Optional

import customtkinter as ctk

from widgets.delete_control import confirm_delete, make_delete_button


class SegmentRowList(ctk.CTkFrame):
    """Reusable list of Start/End entry-field rows with add/remove/select.

    Used standalone (trim bulk mode — just add/remove rows) and with
    `selectable=True` (cut panel — one row selected at a time, whose
    handles are draggable on the timeline).
    """

    def __init__(self, parent, selectable: bool = False,
                 on_change: Optional[Callable[[], None]] = None,
                 on_select: Optional[Callable[[int], None]] = None,
                 default_range: Optional[Callable[[], tuple[str, str]]] = None,
                 on_capture: Optional[Callable[[int, bool], None]] = None):
        """on_capture(idx, is_start): if given, a ⏺ button beside each of Start/End calls it
        (the owner fills that field from the player's current time)."""
        super().__init__(parent, fg_color="transparent")
        self.on_capture = on_capture
        self.selectable = selectable
        self.on_change = on_change
        self.on_select = on_select
        self.default_range = default_range
        self.rows: list[dict] = []
        self.selected_index: Optional[int] = None

        self.grid_columnconfigure(0, weight=1)
        self.rows_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.rows_frame.grid(row=0, column=0, sticky="ew")
        self.rows_frame.grid_columnconfigure(0, weight=1)

        self.add_btn = ctk.CTkButton(self, text="+ Add range", command=lambda: self.add_row())
        self.add_btn.grid(row=1, column=0, pady=(6, 0), sticky="w")

    def add_row(self, start: str = "", end: str = ""):
        if not start and not end and self.default_range:
            start, end = self.default_range()
        idx = len(self.rows)
        row_frame = ctk.CTkFrame(self.rows_frame, fg_color="transparent")
        row_frame.grid(row=idx, column=0, pady=2, sticky="ew")

        ctk.CTkLabel(row_frame, text=f"{idx + 1}.", width=24).pack(side="left")

        cap = self.on_capture is not None  # compact row: ⏺ buttons, no Select button
        entry_w = 92 if cap else 120
        start_entry = ctk.CTkEntry(row_frame, placeholder_text="Start", width=entry_w)
        start_entry.insert(0, start)
        start_entry.pack(side="left", padx=(4, 2 if cap else 4))
        start_entry.bind("<FocusOut>", lambda e: self._notify_change())
        start_entry.bind("<Return>", lambda e: self._notify_change())

        entry = {"frame": row_frame, "start": start_entry, "initial": (start, end)}
        if cap:
            entry["start_mark"] = ctk.CTkButton(row_frame, text="⏺", width=28)
            entry["start_mark"].pack(side="left", padx=(0, 4))

        end_entry = ctk.CTkEntry(row_frame, placeholder_text="End", width=entry_w)
        end_entry.insert(0, end)
        end_entry.pack(side="left", padx=(0, 2 if cap else 4))
        end_entry.bind("<FocusOut>", lambda e: self._notify_change())
        end_entry.bind("<Return>", lambda e: self._notify_change())
        entry["end"] = end_entry
        if cap:
            entry["end_mark"] = ctk.CTkButton(row_frame, text="⏺", width=28)
            entry["end_mark"].pack(side="left", padx=(0, 4))
            # no Select button: focusing a field selects its row
            for w in (start_entry, end_entry):
                w.bind("<FocusIn>", lambda e, f=row_frame: self._select(self._index_of(f)), add="+")

        if self.selectable and not cap:
            select_btn = ctk.CTkButton(row_frame, text="Select", width=64,
                                        command=lambda: self._select(idx))
            select_btn.pack(side="left", padx=(0, 4))
            entry["select_btn"] = select_btn

        # far right edge, away from the ⏺/Select buttons, and confirmed (see _request_delete)
        delete_btn = make_delete_button(row_frame, lambda: self._request_delete(idx))
        delete_btn.pack(side="right", padx=(0, 2))
        entry["delete_btn"] = delete_btn

        self.rows.append(entry)
        self._wire_row(idx)
        self._notify_change()
        if self.selectable:
            self._select(idx)

    def _request_delete(self, idx: int):
        """Ask before deleting a row the user has filled in; untouched rows (still at the values
        they were created with, or empty) go without a dialog."""
        if idx >= len(self.rows):
            return
        entry = self.rows[idx]
        current = (entry["start"].get().strip(), entry["end"].get().strip())
        if current != tuple(v.strip() for v in entry["initial"]) and any(current):
            if not confirm_delete("Delete range",
                                  f"Delete range {idx + 1} ({current[0] or '?'} → {current[1] or '?'})?",
                                  parent=self.winfo_toplevel()):
                return
        self._delete(idx)

    def _delete(self, idx: int):
        if idx >= len(self.rows):
            return
        self.rows[idx]["frame"].destroy()
        del self.rows[idx]
        if self.selected_index == idx:
            self.selected_index = None
        self._relayout()
        self._notify_change()
        if self.selectable and self.rows and self.selected_index is None:
            self._select(0)

    def _index_of(self, frame) -> int:
        return next(i for i, e in enumerate(self.rows) if e["frame"] is frame)

    def _wire_row(self, i: int):
        entry = self.rows[i]
        if "start_mark" in entry:
            entry["start_mark"].configure(command=lambda j=i: self._capture(j, True))
            entry["end_mark"].configure(command=lambda j=i: self._capture(j, False))

    def _capture(self, idx: int, is_start: bool):
        self._select(idx)
        if self.on_capture:
            self.on_capture(idx, is_start)

    def _relayout(self):
        for i, entry in enumerate(self.rows):
            self._wire_row(i)
            entry["frame"].grid(row=i, column=0, pady=2, sticky="ew")
            for child in entry["frame"].winfo_children():
                if isinstance(child, ctk.CTkLabel):
                    child.configure(text=f"{i + 1}.")
            if "select_btn" in entry:
                entry["select_btn"].configure(command=lambda j=i: self._select(j))
            entry["delete_btn"].configure(command=lambda j=i: self._request_delete(j))

    def _select(self, idx: int):
        self.selected_index = idx
        for i, entry in enumerate(self.rows):
            if self.on_capture is not None:
                entry["frame"].configure(border_width=2 if i == idx else 0, border_color="#2563eb")
            if "select_btn" in entry:
                entry["select_btn"].configure(
                    fg_color=("#2563eb", "#1d4ed8") if i == idx
                    else ctk.ThemeManager.theme["CTkButton"]["fg_color"]
                )
        if self.on_select:
            self.on_select(idx)

    def _notify_change(self):
        if self.on_change:
            self.on_change()

    def get_segments(self) -> list[tuple[str, str]]:
        return [(e["start"].get().strip(), e["end"].get().strip()) for e in self.rows]

    def set_row(self, idx: int, start: str, end: str):
        if idx >= len(self.rows):
            return
        entry = self.rows[idx]
        entry["start"].delete(0, "end")
        entry["start"].insert(0, start)
        entry["end"].delete(0, "end")
        entry["end"].insert(0, end)

    def clear(self):
        for entry in self.rows:
            entry["frame"].destroy()
        self.rows = []
        self.selected_index = None
