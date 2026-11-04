import customtkinter as ctk

from core import settings


class PreviewOptions(ctk.CTkFrame):
    """One line of checkboxes under a range list: 'jump when a time field is clicked' and,
    for Cut, 'preview with join'. `focus_var` shares another instance's jump variable (and hides
    its checkbox), so two lists on one panel never disagree."""

    def __init__(self, parent, show_join: bool = False, focus_var=None):
        super().__init__(parent, fg_color="transparent")
        font = ctk.CTkFont(size=12)
        if focus_var is None:
            self.focus_var = ctk.BooleanVar(value=bool(settings.get("seek_on_focus", True)))
            self.focus_var.trace_add("write", lambda *_: settings.set("seek_on_focus", self.focus_var.get()))
            ctk.CTkCheckBox(self, text="Jump when a time field is clicked", variable=self.focus_var,
                            checkbox_width=18, checkbox_height=18, font=font).pack(anchor="w", pady=2)
        else:
            self.focus_var = focus_var

        self.join_var = ctk.BooleanVar(value=bool(settings.get("cut_preview_join", True)))
        self.join_var.trace_add("write", lambda *_: settings.set("cut_preview_join", self.join_var.get()))
        if show_join:
            ctk.CTkCheckBox(self, text="▶ plays 2 s before and after the cut (join)", variable=self.join_var,
                            checkbox_width=18, checkbox_height=18, font=font).pack(anchor="w", pady=2)

    @property
    def jump_on_focus(self) -> bool:
        return self.focus_var.get()

    @property
    def join(self) -> bool:
        return self.join_var.get()
