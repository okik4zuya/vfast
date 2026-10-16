"""Generic per-video "spec" persistence shared by the Effects, Cut and Trim panels.

A spec is a small JSON file next to the video, named after it (`clip.mp4` -> `clip.cut.json`). The panel is
only a view of it:

    file --(switch_video)--> session.spec --(_sync_widgets inside session.applying())--> widgets
    widgets --(user edit -> session.update)--> session.spec --(debounced, atomic)--> file

so a panel that is destroyed on navigation, or a video switch, can never leak one video's settings into
another. A video that was only looked at, or whose spec is back to default, has no sidecar file.

Each panel supplies a `Schema` (what a valid/default spec is); everything else lives here. Nothing in this
module touches tkinter: the session gets `schedule(ms, fn) -> handle` / `cancel(handle)` injected (the panel
passes tk's after/after_cancel, tests pass a fake clock).
"""
import copy
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable

SOURCE_KEYS = ("size", "mtime", "duration", "width", "height")


@dataclass(frozen=True)
class Schema:
    suffix: str                                              # ".cut.json"
    version: int
    editable: tuple                                          # keys the UI may change
    default: Callable[[], dict]
    sanitize: Callable[[object], tuple[dict, list[str]]]     # anything -> valid spec + warnings, never raises
    is_default: Callable[[dict], bool]
    normalize: Callable[[dict], None] | None = None          # in-place tidy-up after an update
    list_key: str | None = None                              # a bare JSON list in the file means {list_key: [...]}


@dataclass
class Issue:
    kind: str        # file_changed | resolution_changed | no_audio | effect_out_of_range | bad_time | ...
    message: str
    index: int = -1  # row/effect index the issue is about, when relevant


def sidecar_path(video: str, schema: Schema) -> str:
    return os.path.splitext(video)[0] + schema.suffix


def fingerprint(video: str, duration: float, width: int, height: int) -> dict | None:
    try:
        st = os.stat(video)
    except OSError:
        return None
    return {"size": st.st_size, "mtime": st.st_mtime, "duration": duration, "width": width, "height": height}


def source_changed(spec: dict, current: dict) -> list[Issue]:
    """The video behind a saved spec was replaced / re-rendered / re-encoded since the spec was saved."""
    saved = spec.get("source")
    if not saved:
        return []
    out = []
    if saved["size"] != current["size"] or abs(saved["mtime"] - current["mtime"]) > 1.0:
        out.append(Issue("file_changed", "File video berubah sejak spec disimpan; "
                                         "waktu di spec mungkin tidak cocok."))
    sw, sh, cw, ch = saved["width"], saved["height"], current["width"], current["height"]
    if sw and sh and cw and ch and (sw, sh) != (cw, ch):
        out.append(Issue("resolution_changed", f"Resolusi berubah ({sw}x{sh} -> {cw}x{ch})."))
    return out


# ---- files --------------------------------------------------------------------------------------
def read_file(path: str, schema: Schema) -> tuple[dict | None, list[str]]:
    """(spec, warnings). spec is None when the file cannot be used (unreadable, not an object, or from a
    newer app version); warnings then says why. A usable file is always sanitized."""
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, list) and schema.list_key:
            raw = {schema.list_key: raw}
        if not isinstance(raw, dict):
            raise ValueError("bukan objek JSON")
        if int(raw.get("version", 1)) > schema.version:
            raise ValueError(f"spec versi {raw.get('version')} lebih baru dari aplikasi")
    except (OSError, ValueError, TypeError) as exc:
        return None, [f"spec tidak bisa dibaca ({exc})"]
    return schema.sanitize(raw)


def write_file(path: str, spec: dict, schema: Schema) -> None:
    """Atomic: write a temp file, then replace."""
    clean, _ = schema.sanitize(spec)
    clean["source"] = spec.get("source") or None
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def read_sidecar(video: str, schema: Schema) -> tuple[dict, list[str]]:
    """Missing -> default. Unusable -> moved to .bak (never silently overwritten), default, a warning."""
    path = sidecar_path(video, schema)
    if not os.path.exists(path):
        return schema.default(), []
    spec, warns = read_file(path, schema)
    if spec is not None:
        return spec, warns
    try:
        os.replace(path, path + ".bak")
        where = f"disalin ke {os.path.basename(path)}.bak"
    except OSError:
        where = "tidak bisa di-backup"
    return schema.default(), [f"{warns[0]}; dipakai default; {where}"]


def write_sidecar(video: str, spec: dict, schema: Schema) -> None:
    """A default spec removes the sidecar instead of writing an empty one."""
    path = sidecar_path(video, schema)
    if schema.is_default(spec):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        return
    write_file(path, spec, schema)


# ---- session ------------------------------------------------------------------------------------
class SpecSession:
    """Everything a panel needs that is not a widget. Subclass and override `revalidate` to report problems
    of the saved spec against the video that is actually selected."""

    DEBOUNCE_MS = 500

    def __init__(self, schema: Schema, schedule, cancel, *, reader=None, writer=None):
        self.schema = schema
        self._schedule_fn, self._cancel_fn = schedule, cancel
        self._read = reader or (lambda video: read_sidecar(video, schema))
        self._write = writer or (lambda video, spec: write_sidecar(video, spec, schema))
        self.video: str | None = None
        self.spec = schema.default()
        self.warnings: list[str] = []
        self.issues: list[Issue] = []
        self.generation = 0
        self.running = False
        self.save_error: str | None = None
        self.current: dict | None = None   # fingerprint of the selected video once probed
        self.has_audio = True
        self.loading = False
        self._dirty = False
        self._timer = None
        self._stamp = 0
        self._written = 0

    # ---- switching -------------------------------------------------------------------------
    def switch_video(self, path: str | None) -> bool:
        """False (nothing changed) while a render runs. Otherwise: flush old, load new, reset state."""
        if self.running:
            return False
        if path == self.video:
            return True
        self.flush()
        self.generation += 1
        self.video = path
        self.current = None
        self.has_audio = True
        self.issues = []
        if path:
            self.spec, self.warnings = self._read(path)
        else:
            self.spec, self.warnings = self.schema.default(), []
        return True

    @contextmanager
    def applying(self):
        """Wrap the UI's spec -> widgets step so widget callbacks don't write the spec back."""
        self.loading = True
        try:
            yield
        finally:
            self.loading = False

    def apply_probe(self, generation: int, current: dict, has_audio: bool = True) -> list[Issue] | None:
        """Probe result for `generation`; a stale one (user already switched again) is ignored -> None."""
        if generation != self.generation or self.video is None:
            return None
        self.current, self.has_audio = current, has_audio
        self.revalidate()
        return self.issues

    def revalidate(self) -> list[Issue]:
        if self.video is None or self.current is None:
            self.issues = []
        else:
            self.issues = source_changed(self.spec, self.current)
        return self.issues

    # ---- editing ---------------------------------------------------------------------------
    def update(self, **changes) -> None:
        if self.loading or self.video is None:
            return
        for k in changes:
            if k not in self.schema.editable:
                raise KeyError(k)
        self.spec.update(copy.deepcopy(changes))
        if self.schema.normalize:
            self.schema.normalize(self.spec)
        self._dirty = True
        self._arm()

    def accept_source(self) -> None:
        """User chose 'keep the spec' despite a changed file: re-stamp the saved source."""
        if self.video and self.current:
            self.spec["source"] = {k: self.current[k] for k in SOURCE_KEYS}
            self._dirty = True
            self._arm()
            self.revalidate()

    def reset(self) -> None:
        if self.video is None:
            return
        self.spec = self.schema.default()
        self._dirty = True
        self.flush()
        self.revalidate()

    def _take(self, other: dict) -> None:
        self.update(**{k: other[k] for k in self.schema.editable})
        self.revalidate()

    def copy_from(self, other_video: str) -> list[str]:
        """Explicit user action: take another video's spec (never its source stamp)."""
        if self.video is None:
            return []
        other, warns = self._read(other_video)
        self._take(other)
        return warns

    # ---- explicit save / load by file name ---------------------------------------------------
    def default_export_path(self) -> str | None:
        return sidecar_path(self.video, self.schema) if self.video else None

    def export_to(self, path: str) -> None:
        """Save the current spec to `path` (any name), even when it equals the default. May raise OSError."""
        if self.video is None:
            return
        spec = copy.deepcopy(self.spec)
        if not spec.get("source") and self.current:
            spec["source"] = {k: self.current[k] for k in SOURCE_KEYS}
        write_file(path, spec, self.schema)

    def import_from(self, path: str) -> tuple[bool, list[str]]:
        """Load a spec file into the current video: the same settings, never the file's source stamp.
        (ok, warnings). An unusable file changes nothing: ok is False and warnings says why (the user's
        file is never renamed)."""
        if self.video is None:
            return False, ["tidak ada video terpilih"]
        other, warns = read_file(path, self.schema)
        if other is None:
            return False, warns
        self._take(other)
        return True, warns

    # ---- persistence -----------------------------------------------------------------------
    def _arm(self) -> None:
        if self._timer is not None:
            self._cancel_fn(self._timer)
        self._stamp += 1
        job = (self._stamp, self.video, copy.deepcopy(self.spec), self.current)
        self._timer = self._schedule_fn(self.DEBOUNCE_MS, lambda: self._commit(*job))

    def _commit(self, stamp: int, video: str, spec: dict, current: dict | None) -> None:
        # A job older than something already written must never overwrite it (late timer after switching back).
        if stamp < self._written:
            return
        self._written = stamp
        if not spec.get("source") and current:
            spec["source"] = {k: current[k] for k in SOURCE_KEYS}
        try:
            self._write(video, spec)
            self.save_error = None
        except OSError as exc:
            self.save_error = f"gagal menyimpan spec: {exc}"
        if video == self.video and stamp == self._stamp:
            self._dirty = False
            self._timer = None
            if spec.get("source"):
                self.spec["source"] = spec["source"]

    def flush(self) -> None:
        """Write now whatever is pending, to the video it belongs to."""
        if self._timer is not None:
            self._cancel_fn(self._timer)
            self._timer = None
        if self._dirty and self.video:
            self._stamp += 1
            self._commit(self._stamp, self.video, copy.deepcopy(self.spec), self.current)
        self._dirty = False
