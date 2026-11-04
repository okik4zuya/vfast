"""Jump-to / preview helpers for the Cut and Trim range fields (no tkinter: the player and the
timer are injected, so the logic is testable with fakes).

`player` needs: is_running(), seek_to(seconds, pause), pause(), seek_to_throttled(seconds),
get_time_pos_async(callback). `schedule(ms, fn)` / `cancel(job)` are Tk's `after` / `after_cancel`."""
from core.cut import parse_time

_POLL_MS = 100
_LAND_BEFORE, _LAND_AFTER = 0.3, 1.5   # a seek "landed" when time-pos is this close to its target
_GIVE_UP_POLLS = 30                    # ~3 s without ever landing (seek lost / mpv busy)
_STALL_POLLS = 8                       # position stopped advancing (end of file, paused by the user)


class RangePreview:
    """Plays a list of (from, until) phases back to back, then pauses on the last `until`.
    Position is polled over IPC; a phase ends once time-pos reaches `until`."""

    def __init__(self, player, schedule, cancel):
        self.player, self._schedule, self._cancel_job = player, schedule, cancel
        self._gen = 0
        self._job = None
        self._phases: list[tuple[float, float]] = []
        self._from = self._until = 0.0
        self._landed = False
        self._polls = self._stalled = 0
        self._last = None
        self.running = False

    def start(self, phases: list[tuple[float, float]]):
        self.cancel(pause=False)
        self._gen += 1
        self._phases = list(phases)
        self.running = True
        self._begin_phase(self._gen)

    def cancel(self, pause: bool = False):
        self._gen += 1
        if self._job is not None:
            try:
                self._cancel_job(self._job)
            except Exception:
                pass
            self._job = None
        was_running, self.running = self.running, False
        if pause and was_running:
            self.player.pause()

    def _begin_phase(self, gen: int):
        if gen != self._gen:
            return
        if not self._phases:
            self._finish()
            return
        self._from, self._until = self._phases.pop(0)
        self._landed = False
        self._polls = self._stalled = 0
        self._last = None
        self.player.seek_to(self._from, pause=False)
        self._poll_later(gen)

    def _poll_later(self, gen: int):
        self._job = self._schedule(_POLL_MS, lambda: self._poll(gen))

    def _poll(self, gen: int):
        if gen != self._gen:
            return
        self._job = None
        self.player.get_time_pos_async(lambda pos: self._on_pos(gen, pos))

    def _on_pos(self, gen: int, pos):
        if gen != self._gen:
            return
        if pos is None:  # mpv went away
            self.cancel()
            return
        self._polls += 1
        if not self._landed:
            if self._from - _LAND_BEFORE <= pos <= self._from + _LAND_AFTER:
                self._landed = True
            elif self._polls > _GIVE_UP_POLLS:
                self._finish()
                return
        if self._landed:
            if pos >= self._until - 0.02:
                self._begin_phase(gen)
                return
            self._stalled = self._stalled + 1 if self._last is not None and abs(pos - self._last) < 1e-3 else 0
            self._last = pos
            if self._stalled >= _STALL_POLLS:
                self._begin_phase(gen)
                return
        self._poll_later(gen)

    def _finish(self):
        """Polling overshoots `until` by up to a poll interval: put the player exactly on it."""
        self.running = False
        self._job = None
        self.player.seek_to(self._until, pause=True)


class RangeNav:
    """What the Start / Preview / End buttons, field focus and timeline scrubbing do to the player."""

    def __init__(self, player, schedule, cancel, log=print, tag: str = "Range"):
        self.player, self.log, self.tag = player, log, tag
        self._preview = RangePreview(player, schedule, cancel)

    def _ready(self) -> bool:
        if not self.player.is_running():
            self.log(f"[{self.tag}] mpv preview is not running.")
            return False
        return True

    def stop(self):
        self._preview.cancel()

    def goto(self, seconds: float):
        """Paused jump (field focus, ⏮ Start, End ⏭). Silent when mpv isn't running."""
        self._preview.cancel()
        if self.player.is_running():
            self.player.seek_to(seconds, pause=True)

    def goto_text(self, text: str, label: str):
        try:
            seconds = parse_time(text)
        except ValueError:
            self.log(f"[{self.tag}] {label} is empty or not a valid time.")
            return
        if self._ready():
            self.goto(seconds)

    def scrub(self, seconds: float):
        self._preview.cancel()
        self.player.seek_to_throttled(seconds)

    def preview(self, start_text: str, end_text: str, join: bool = False,
                lead: float = 2.0, tail: float = 2.0, duration: float = 0.0):
        """Plays Start -> End. With `join` (Cut: the range is removed) it instead plays what the viewer
        will see after the cut: `lead` s before Start, then straight on from End for `tail` s."""
        try:
            start, end = parse_time(start_text), parse_time(end_text)
        except ValueError:
            self.log(f"[{self.tag}] Start and End must both be valid times to preview.")
            return
        if end <= start:
            self.log(f"[{self.tag}] End is not after Start.")
            return
        if not self._ready():
            return
        if join:
            stop_at = min(end + tail, duration) if duration > 0 else end + tail
            phases = [(max(0.0, start - lead), start), (end, max(end, stop_at))]
        else:
            phases = [(start, end)]
        self._preview.start(phases)
