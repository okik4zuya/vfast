"""Per-video specs for the Cut and Trim panels (`<video>.cut.json`, `<video>.trim.json`).

Times are kept as the strings the user sees (`00:01:02.500`), exactly like the entry fields, so a half-typed
value is never lost or "corrected" behind the user's back; problems are reported by `validate_*` instead.

    cut : {"version": 1, "ranges": [["start", "end"], ...], "source": {...}}      ranges to REMOVE
    trim: {"version": 1, "start": "", "end": "", "bulk": [["start", "end"], ...], "source": {...}}
          start/end "" = the whole video (so the default follows whatever video is loaded)

Generic machinery (files, switching, saves, explicit save/load) is core/sidecar.py.
"""
from core.cut import parse_time
from core.sidecar import SOURCE_KEYS, Issue, Schema, SpecSession, source_changed

SPEC_VERSION = 1
MAX_ROWS = 500


def _pairs(raw, label: str, warnings: list[str]) -> list[list[str]]:
    out: list[list[str]] = []
    if not isinstance(raw, list):
        return out
    for i, row in enumerate(raw[:MAX_ROWS]):
        if (isinstance(row, (list, tuple)) and len(row) == 2
                and all(isinstance(x, (str, int, float)) for x in row)):
            out.append([str(row[0]).strip(), str(row[1]).strip()])
        else:
            warnings.append(f"{label} #{i + 1} dibuang: bukan pasangan [mulai, akhir]")
    if len(raw) > MAX_ROWS:
        warnings.append(f"{label}: hanya {MAX_ROWS} baris pertama dipakai")
    return out


def _source(raw: dict):
    src = raw.get("source")
    return {k: src[k] for k in SOURCE_KEYS} if isinstance(src, dict) and all(k in src for k in SOURCE_KEYS) else None


# ---- Cut --------------------------------------------------------------------------------------
def default_cut() -> dict:
    return {"version": SPEC_VERSION, "ranges": [], "source": None}


def sanitize_cut(raw) -> tuple[dict, list[str]]:
    spec, warnings = default_cut(), []
    if not isinstance(raw, dict):
        return spec, ["isi spec bukan objek, dipakai default"]
    spec["ranges"] = _pairs(raw.get("ranges"), "range", warnings)
    spec["source"] = _source(raw)
    return spec, warnings


def is_default_cut(spec: dict) -> bool:
    return not spec.get("ranges")


CUT = Schema(suffix=".cut.json", version=SPEC_VERSION, editable=("ranges",), default=default_cut,
             sanitize=sanitize_cut, is_default=is_default_cut)


# ---- Trim -------------------------------------------------------------------------------------
def default_trim() -> dict:
    return {"version": SPEC_VERSION, "start": "", "end": "", "bulk": [], "source": None}


def sanitize_trim(raw) -> tuple[dict, list[str]]:
    spec, warnings = default_trim(), []
    if not isinstance(raw, dict):
        return spec, ["isi spec bukan objek, dipakai default"]
    for key in ("start", "end"):
        v = raw.get(key)
        spec[key] = str(v).strip() if isinstance(v, (str, int, float)) else ""
    spec["bulk"] = _pairs(raw.get("bulk"), "klip", warnings)
    spec["source"] = _source(raw)
    return spec, warnings


def is_default_trim(spec: dict) -> bool:
    return not (spec.get("start") or spec.get("end") or spec.get("bulk"))


TRIM = Schema(suffix=".trim.json", version=SPEC_VERSION, editable=("start", "end", "bulk"),
              default=default_trim, sanitize=sanitize_trim, is_default=is_default_trim)


# ---- validation -------------------------------------------------------------------------------
def _check_row(label: str, idx: int, start: str, end: str, duration: float) -> list[Issue]:
    """Problems of one start/end pair against the loaded video. Empty cells are not problems (unfinished rows)."""
    if not start and not end:
        return []
    try:
        s = parse_time(start) if start else None
        e = parse_time(end) if end else None
    except ValueError:
        return [Issue("bad_time", f"{label} {idx + 1}: waktu tidak valid ({start or '?'} -> {end or '?'}).", idx)]
    out = []
    if s is not None and e is not None and e <= s:
        out.append(Issue("bad_range", f"{label} {idx + 1}: akhir tidak setelah mulai.", idx))
    if duration > 0 and s is not None and s >= duration:
        out.append(Issue("range_out_of_range",
                         f"{label} {idx + 1}: mulai di {start}, setelah video berakhir ({duration:.1f}s).", idx))
    return out


def validate_cut(spec: dict, current: dict) -> list[Issue]:
    issues = source_changed(spec, current)
    for i, (s, e) in enumerate(spec.get("ranges") or []):
        issues += _check_row("Range", i, s, e, current.get("duration") or 0.0)
    return issues


def validate_trim(spec: dict, current: dict) -> list[Issue]:
    issues = source_changed(spec, current)
    dur = current.get("duration") or 0.0
    s, e = spec.get("start") or "", spec.get("end") or ""
    if s or e:
        issues += _check_row("Trim", 0, s, e, dur)
        try:
            if e and dur > 0 and parse_time(e) > dur + 0.5:
                issues.append(Issue("end_beyond_video", f"Trim: akhir ({e}) melewati durasi video ({dur:.1f}s)."))
        except ValueError:
            pass
    for i, (bs, be) in enumerate(spec.get("bulk") or []):
        issues += _check_row("Klip", i, bs, be, dur)
    return issues


class CutSession(SpecSession):
    def __init__(self, schedule, cancel, **kw):
        super().__init__(CUT, schedule, cancel, **kw)

    def revalidate(self) -> list[Issue]:
        self.issues = [] if self.video is None or self.current is None else validate_cut(self.spec, self.current)
        return self.issues


class TrimSession(SpecSession):
    def __init__(self, schedule, cancel, **kw):
        super().__init__(TRIM, schedule, cancel, **kw)

    def revalidate(self) -> list[Issue]:
        self.issues = [] if self.video is None or self.current is None else validate_trim(self.spec, self.current)
        return self.issues
