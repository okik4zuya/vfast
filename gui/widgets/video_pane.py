import customtkinter as ctk

from widgets.mpv_embed import MpvEmbed

_KEYS_HINT = ("Keys (click video first): Space = play/pause, ←/→ = 5s, Shift+←/→ = 1s, "
              "Home/End = start/end")


class VideoPane(ctk.CTkFrame):
    """Left pane shared by Cut, Trim and Overlay: video dropdown, embedded mpv preview, transport
    buttons and a hint. Add it straight to the panel's PanedWindow.

    The dropdown, `MpvEmbed` and transport buttons live in a fixed, non-scrolling `top` frame: mpv is
    a real Win32 child window (--wid) and cannot sit inside a Canvas-backed CTkScrollableFrame, and
    the transport must never scroll out of reach. Only the hint scrolls. To guarantee that, the
    preview's height is capped to what is left of the pane after the other controls — a vertical
    video would otherwise take 1.8x its width in height.

    Transport buttons are explicit, not just keybindings: they go over the mpv IPC pipe, which does
    not depend on cross-process Win32 keyboard focus (never confirmed to work, see MpvEmbed)."""

    _MIN_PREVIEW = 120  # never cap the preview below this, even in a very short window
    _HINT_ROOM = 44     # keep a sliver for the hint's scroll area

    def __init__(self, parent, on_video_change, hint: str = ""):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # the scrolling part takes whatever room `top` doesn't use

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="new")
        top.grid_columnconfigure(0, weight=1)
        self.video_menu = ctk.CTkOptionMenu(top, values=["(no videos found)"],
                                            command=lambda _: on_video_change())
        self.video_menu.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.mpv_embed = MpvEmbed(top)
        self.mpv_embed.grid(row=1, column=0, sticky="ew")

        # Equal-weight columns that may shrink: 7 fixed-width buttons overflowed the pane's minimum.
        self._transport = ctk.CTkFrame(top, fg_color="transparent")
        self._transport.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        mpv = self.mpv_embed
        for i, (text, cmd) in enumerate((
            ("⏮ Start", mpv.seek_start),
            ("⏪ 5s", lambda: mpv.seek_relative(-5)),
            ("◀ 1s", lambda: mpv.seek_relative(-1)),
            ("⏯", mpv.toggle_pause),
            ("1s ▶", lambda: mpv.seek_relative(1)),
            ("5s ⏩", lambda: mpv.seek_relative(5)),
            ("End ⏭", mpv.seek_end),
        )):
            self._transport.grid_columnconfigure(i, weight=1, uniform="transport")
            ctk.CTkButton(self._transport, text=text, width=10, command=cmd,
                          font=ctk.CTkFont(size=12)).grid(row=0, column=i, sticky="ew",
                                                         padx=(0 if i == 0 else 2, 0))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        # own row with a wraplength so it cannot spill sideways at small widths
        ctk.CTkLabel(scroll, text=(hint + " " if hint else "") + _KEYS_HINT,
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=330,
                     justify="left", anchor="w").pack(anchor="w")

        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        # CTkFrame forwards <Configure> from its internal canvas, so event.widget is not `self`.
        used = (self.video_menu.winfo_reqheight() + 8 + self._transport.winfo_reqheight() + 8
                + 8 + self._HINT_ROOM)
        self.mpv_embed.set_max_height(max(self._MIN_PREVIEW, event.height - used))
