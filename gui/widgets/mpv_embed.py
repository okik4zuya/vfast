import ctypes
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from typing import Callable, Optional

import customtkinter as ctk

from core.paths import mpv_path
from core.mpv_ipc import query_property, send_command

_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_ASPECT = 9 / 16


def _find_mpv_child_hwnd(parent_hwnd: int) -> Optional[int]:
    """mpv reparents its own window to be a direct child of the HWND we pass
    via --wid — find that child so we can hand it real Win32 keyboard focus.
    Windows never moves keyboard focus to a child window just because the
    mouse is over it (only mouse messages route by hit-testing); something
    has to call SetFocus() explicitly, which is the host's job here since
    the embedded window has no title bar/border to click for activation."""
    if sys.platform != "win32":
        return None
    found = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, lparam):
        found.append(hwnd)
        return False  # stop at the first child

    ctypes.windll.user32.EnumChildWindows(parent_hwnd, WNDENUMPROC(_cb), 0)
    return found[0] if found else None


class MpvEmbed(ctk.CTkFrame):
    """Docked mpv playback surface, embedded via --wid. IPC is one-shot
    query-only — no continuous position sync back to the Timeline."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="#000000")
        self.proc: Optional[subprocess.Popen] = None
        self.pipe_name: Optional[str] = None
        self._aspect = _ASPECT
        self._max_height = 0  # 0 = uncapped; see set_max_height

        # Plain tk.Frame, not CTkFrame: CTkFrame draws rounded-corner canvas
        # art over children which can conflict with mpv's child HWND painting.
        self.surface = tk.Frame(self, bg="black", highlightthickness=0)
        self.surface.place(relx=0, rely=0, relwidth=1, relheight=1)  # re-placed by _refit when capped
        self.surface.bind("<Button-1>", self._focus_mpv)

        # Keybindings live on our own Tk surface, not on mpv's embedded HWND —
        # Tk keyboard focus is same-process and always works via focus_set(),
        # unlike the cross-process OS focus _focus_mpv() attempts below (which
        # has never been confirmed to actually work). Keys are translated into
        # the same IPC calls the transport buttons use, so they're just as
        # reliable as those buttons regardless of whether mpv itself ever gets
        # real OS keyboard focus.
        self.surface.bind("<space>", self._on_key_toggle_pause)
        self.surface.bind("<Left>", lambda e: self._on_key_seek(-5))
        self.surface.bind("<Right>", lambda e: self._on_key_seek(5))
        self.surface.bind("<Shift-Left>", lambda e: self._on_key_seek(-1))
        self.surface.bind("<Shift-Right>", lambda e: self._on_key_seek(1))
        self.surface.bind("<Home>", self._on_key_seek_start)
        self.surface.bind("<End>", self._on_key_seek_end)

        self.pack_propagate(False)
        self.bind("<Configure>", self._on_configure)
        self.bind("<Destroy>", self._on_destroy)

    def _focus_mpv(self, event=None):
        """Give the embedded mpv window real OS keyboard focus so its own
        keybindings (space to pause, arrows to seek, etc.) work. Without
        this, clicking the video only ever reaches Tk's surface frame —
        mpv's child HWND never becomes the focused window.

        A plain cross-process SetFocus() typically fails silently: Win32
        keeps a separate input queue per thread, and mpv's embedded window
        belongs to mpv's own process/thread, not ours. AttachThreadInput
        merges the two threads' input queues for the duration of the call
        so SetFocus actually takes effect, then detaches again."""
        self.surface.focus_set()  # Tk-level focus for our own key bindings above
        if not self.is_running():
            return
        hwnd = _find_mpv_child_hwnd(self.surface.winfo_id())
        if not hwnd:
            return
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        target_tid = user32.GetWindowThreadProcessId(hwnd, None)
        current_tid = kernel32.GetCurrentThreadId()
        attached = False
        if target_tid and target_tid != current_tid:
            attached = bool(user32.AttachThreadInput(current_tid, target_tid, True))
        try:
            user32.SetFocus(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(current_tid, target_tid, False)

    def set_aspect(self, width: int, height: int):
        """Set the preview's aspect ratio from the actual video's dimensions
        so the container matches the video exactly and mpv doesn't have to
        letterbox (black bars) inside a mismatched-aspect widget."""
        self._aspect = (height / width) if width and height else _ASPECT
        self._refit(self.winfo_width())

    def set_max_height(self, px: int):
        """Cap the preview's height (the owner knows how much vertical room is left). A tall/vertical
        video would otherwise push everything below the preview off-screen."""
        if px != self._max_height:
            self._max_height = px
            self._refit(self.winfo_width())

    def _refit(self, width: int):
        # Width-driven: fill the column, height follows from the video's aspect. When that height
        # exceeds the cap, the frame shrinks to the cap and the video surface narrows to match the
        # aspect (centered on the black frame) — shrinking only the height would letterbox/pillarbox
        # inside mpv, which is what an earlier fixed max_height did.
        if width <= 1:
            return
        full_h = max(1, int(width * self._aspect))
        capped = bool(self._max_height) and full_h > self._max_height
        h = self._max_height if capped else full_h
        if abs(self.winfo_reqheight() - h) > 1:
            self.configure(height=h)
        if capped:
            self.surface.place(relx=0.5, rely=0, anchor="n", width=max(1, int(h / self._aspect)),
                               height=h, relwidth="", relheight="")
        else:
            # place() options accumulate: clear width/height or they ADD to relwidth/relheight.
            self.surface.place(relx=0, rely=0, anchor="nw", relwidth=1, relheight=1,
                               width="", height="")

    def _on_configure(self, event):
        self._refit(event.width)

    def load(self, path: str, start: Optional[str] = None):
        """Tear down any running mpv and relaunch it embedded, on `path`."""
        self.stop()
        self.update_idletasks()  # force geometry so winfo_id()/size are accurate
        self.pipe_name = rf"\\.\pipe\vfast-mpv-{os.getpid()}-{id(self)}-{int(time.time()*1000)}"
        wid = self.surface.winfo_id()
        cmd = [
            mpv_path(), path,
            f"--wid={wid}",
            "--osd-fractions", "--osd-level=3",
            # Native OSC seekbar: mouse events route directly to mpv's own
            # child HWND (Win32 hit-tests by screen position, not OS focus),
            # so click-drag scrubbing works even though keyboard focus
            # forwarding to this window never did (see _focus_mpv above).
            # "always" instead of the "auto" default (hide after mouse-idle)
            # so the bar stays discoverable in a small embedded preview.
            # osc-visibility is a script-opt of the osc.lua script, not a
            # top-level CLI flag (--osc-visibility doesn't exist as an option).
            # Two separate filename labels to strip, confirmed via
            # `strings bin/mpv.exe` + real screenshots (osc.lua isn't
            # extractable any other way from this statically-built binary):
            # osc-windowcontrols=no removes the top-left "${media-title}"
            # bar (only drawn because --border=no leaves no native title
            # bar for it to fall back to) along with its unusable
            # minimize/maximize/close buttons; osc-title= blanks the
            # separate title label the bottom control bar also draws.
            # Both redundant here — the panel's own dropdown already shows
            # which video is loaded.
            "--osc=yes",
            "--script-opts=osc-visibility=always,osc-windowcontrols=no,osc-title=",
            f"--input-ipc-server={self.pipe_name}",
            "--keep-open=yes",
            "--border=no",
            # Flip-model D3D11 presentation isn't clipped to the parent HWND
            # on Windows, so the embedded video floats outside the panel's
            # bounds instead of tracking it. BitBlt presentation respects
            # normal child-window clipping.
            "--d3d11-flip=no",
        ]
        if start:
            cmd.append(f"--start={start}")
        self.proc = subprocess.Popen(
            cmd, creationflags=_CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )  # let OSError propagate to caller
        self.after(300, self._focus_mpv)  # give mpv time to create+reparent its window

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            except Exception:
                pass
        self.proc = None
        self.pipe_name = None

    def send_command_async(self, command: list):
        """Fire-and-forget IPC command (play/pause, seek, ...). Explicit
        buttons that go through this bypass the keyboard-focus problem
        entirely — SetFocus/AttachThreadInput on the embedded mpv HWND has
        never been confirmed to actually work, but the IPC pipe (used by
        Set Start/Set End already) doesn't depend on window focus at all."""
        if not self.is_running() or not self.pipe_name:
            return
        pipe_name = self.pipe_name
        threading.Thread(target=send_command, args=(pipe_name, command), daemon=True).start()

    def toggle_pause(self):
        self.send_command_async(["cycle", "pause"])

    def seek_relative(self, seconds: float):
        # Plain "relative" is a fast/imprecise keyframe seek — mpv snaps to
        # whatever keyframe is nearest instead of the exact offset, which is
        # why short 1s/5s nudges were landing ~5-10s away on web-sourced
        # video with sparse keyframes. "exact" forces frame-accurate seeking.
        self.send_command_async(["seek", seconds, "relative+exact"])

    def seek_start(self):
        """Jump to the first frame and resume playback (matches the "play
        from start" framing of the button/keybinding, unlike seek_end which
        is just a position jump)."""
        self.send_command_async(["seek", 0, "absolute+exact"])
        self.send_command_async(["set_property", "pause", False])

    def seek_end(self):
        # "absolute-percent" 100 asks mpv for the end of the file directly —
        # no need to know the video's actual duration here.
        self.send_command_async(["seek", 100, "absolute-percent+exact"])

    def _on_key_toggle_pause(self, event):
        self.toggle_pause()
        return "break"  # prevent Tk from also inserting a literal space anywhere

    def _on_key_seek(self, seconds: float):
        self.seek_relative(seconds)
        return "break"

    def _on_key_seek_start(self, event):
        self.seek_start()
        return "break"

    def _on_key_seek_end(self, event):
        self.seek_end()
        return "break"

    def get_time_pos_async(self, callback: Callable[[Optional[float]], None]):
        """Query current position off the Tk main thread; result marshaled
        back via after(0, ...). Calls callback(None) if mpv isn't running."""
        if not self.is_running() or not self.pipe_name:
            callback(None)
            return
        pipe_name = self.pipe_name

        def worker():
            value = query_property(pipe_name, "time-pos", timeout=1.5)
            try:
                self.after(0, lambda: callback(value))
            except tk.TclError:
                pass  # widget destroyed while query was in flight

        threading.Thread(target=worker, daemon=True).start()

    def _on_destroy(self, event):
        if event.widget is self:
            self.stop()
