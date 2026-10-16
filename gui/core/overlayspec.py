"""Per-video Overlay spec: `<video>.overlay.json`, the same file the `vfast-overlay` skill CLI and the Effects panel
read (they only look at `effects`, so the extra `version`/`source` keys are harmless, and the old bare-list
and version-less forms still load).

    {"version": 1, "effects": [{"type": "blur", "x": 100, "y": 80, "w": 300, "h": 200, "start": "00:00:05"}, ...],
     "source": {...}}

Rows are saved exactly as the panel shows them, including half-finished ones (a number is stored as a number
when it parses, empty fields are left out), so nothing typed is lost. `effect_problem` (core/overlay.py) says
which rows are not renderable yet; Effects and the CLI skip those and say so.
"""
from core.overlay import EFFECT_TYPES, _t, effect_problem
from core.sidecar import SOURCE_KEYS, Issue, Schema, SpecSession, source_changed

SPEC_VERSION = 1
MAX_EFFECTS = 500
_NUMERIC = ("x", "y", "w", "h", "strength", "block", "size")


def default_overlay() -> dict:
    return {"version": SPEC_VERSION, "effects": [], "source": None}


def clean_effect(fx: dict) -> dict:
    """One row -> JSON-friendly dict: empty values dropped, numeric fields as numbers when they parse."""
    out = {}
    for k, v in fx.items():
        if v is None or (isinstance(v, str) and v.strip() == ""):
            continue
        if k in _NUMERIC:
            try:
                out[k] = int(float(v))
                continue
            except (TypeError, ValueError):
                pass
        out[k] = v.strip() if isinstance(v, str) and k in ("start", "end") else v
    return out


def sanitize_overlay(raw) -> tuple[dict, list[str]]:
    spec, warnings = default_overlay(), []
    if not isinstance(raw, dict):
        return spec, ["isi spec bukan objek, dipakai default"]
    fx = raw.get("effects")
    if isinstance(fx, list):
        for i, e in enumerate(fx[:MAX_EFFECTS]):
            if not isinstance(e, dict) or e.get("type") not in EFFECT_TYPES:
                kind = e.get("type") if isinstance(e, dict) else e
                warnings.append(f"efek #{i + 1} dibuang: tipe tidak dikenal ({kind!r})")
                continue
            spec["effects"].append(clean_effect(e))
        if len(fx) > MAX_EFFECTS:
            warnings.append(f"hanya {MAX_EFFECTS} efek pertama dipakai")
    src = raw.get("source")
    if isinstance(src, dict) and all(k in src for k in SOURCE_KEYS):
        spec["source"] = {k: src[k] for k in SOURCE_KEYS}
    return spec, warnings


def is_default_overlay(spec: dict) -> bool:
    return not spec.get("effects")


OVERLAY = Schema(suffix=".overlay.json", version=SPEC_VERSION, editable=("effects",), default=default_overlay,
                 sanitize=sanitize_overlay, is_default=is_default_overlay, list_key="effects")


def validate_overlay(spec: dict, current: dict) -> list[Issue]:
    """Spec vs the video actually selected. Coordinates are pixels of the input, so a resolution change matters."""
    issues = source_changed(spec, current)
    for i in issues:
        if i.kind == "resolution_changed":
            i.message += " Posisi efek (piksel) mungkin salah."
    dur = current.get("duration") or 0.0
    width, height = current.get("width") or 0, current.get("height") or 0
    for i, fx in enumerate(spec.get("effects") or []):
        label = f"Efek {i + 1} ({fx.get('type')})"
        problem = effect_problem(fx)
        if problem:
            issues.append(Issue("incomplete", f"{label}: {problem}.", i))
            continue
        start = _t(fx.get("start"), 0.0)
        if dur > 0 and start >= dur:
            issues.append(Issue("effect_out_of_range", f"{label}: mulai di {start:g}s, setelah video berakhir ({dur:.1f}s).", i))
        if width and height and "x" in fx and "y" in fx:
            if int(float(fx["x"])) >= width or int(float(fx["y"])) >= height:
                issues.append(Issue("effect_out_of_frame",
                                    f"{label}: posisi ({fx['x']},{fx['y']}) di luar bingkai {width}x{height}.", i))
    return issues


class OverlaySession(SpecSession):
    def __init__(self, schedule, cancel, **kw):
        super().__init__(OVERLAY, schedule, cancel, **kw)

    def revalidate(self) -> list[Issue]:
        self.issues = ([] if self.video is None or self.current is None
                       else validate_overlay(self.spec, self.current))
        return self.issues
