"""Per-video Effects spec (sidecar `<video>.effects.json`). The generic machinery (file handling, switching,
debounced saves, explicit save/load) lives in core/sidecar.py and is shared with the Cut and Trim panels;
this module only says what an Effects spec is.

`<video>.overlay.json` stays the single source for Overlay effects: Effects only reads it, never copies it.
"""
import copy
import json
import os

from core import effects
from core.overlay import _t, effect_problem
from core.sidecar import (SOURCE_KEYS, Issue, Schema, SpecSession, fingerprint,  # noqa: F401  (re-exported)
                          read_sidecar, source_changed, write_sidecar)
from core.speed import MAX_SPEED, MIN_SPEED

SPEC_VERSION = 1
EDITABLE = ("presets", "params", "speed", "use_overlay", "pack")


def spec_path(video: str) -> str:
    return os.path.splitext(video)[0] + ".effects.json"


def overlay_path(video: str) -> str:
    return os.path.splitext(video)[0] + ".overlay.json"


def default_spec() -> dict:
    return {"version": SPEC_VERSION, "presets": [], "params": {}, "speed": 1.0, "use_overlay": True,
            "pack": "", "source": None}


def load_overlay(video: str) -> list[dict]:
    """Overlay effects saved by the Overlay panel, read fresh every call (never cached)."""
    try:
        with open(overlay_path(video), encoding="utf-8") as f:
            data = json.load(f)
        fx = data.get("effects") if isinstance(data, dict) else None
        return [e for e in fx if isinstance(e, dict)] if isinstance(fx, list) else []
    except (OSError, ValueError):
        return []


def usable_overlay(effects: list[dict]) -> list[dict]:
    """The overlay effects complete enough to render. Half-finished rows (the Overlay panel saves them too so
    nothing typed is lost) are skipped here; `validate` tells the user which ones and why."""
    return [fx for fx in effects if effect_problem(fx) is None]


def _prune_params(params: dict) -> dict:
    """Keep only known parameter groups that hold something (so an emptied field leaves no trace)."""
    out = {}
    for group in ("caption", "watermark"):
        g = params.get(group)
        if not isinstance(g, dict):
            continue
        if group == "caption":
            g = {"text": str(g.get("text") or ""), "duration": max(0.0, _num(g.get("duration"), 0.0))}
            if g["text"].strip():
                out[group] = g
        else:
            path = str(g.get("path") or "")
            if path:
                out[group] = {"path": path}
    return out


def _num(v, default: float) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def sanitize(raw) -> tuple[dict, list[str]]:
    """Whatever was on disk -> a valid spec + warnings. Never raises."""
    warnings: list[str] = []
    spec = default_spec()
    if not isinstance(raw, dict):
        return spec, ["isi spec bukan objek, dipakai default"]
    presets, w = effects.normalize(raw.get("presets") if isinstance(raw.get("presets"), list) else [])
    spec["presets"] = presets
    warnings += w
    params = raw.get("params")
    spec["params"] = _prune_params(params) if isinstance(params, dict) else {}
    speed = _num(raw.get("speed"), 1.0)
    if not (MIN_SPEED <= speed <= MAX_SPEED):
        warnings.append(f"speed {speed} di luar {MIN_SPEED}-{MAX_SPEED}, dipakai 1.0")
        speed = 1.0
    spec["speed"] = speed
    spec["use_overlay"] = bool(raw.get("use_overlay", True))
    pack = raw.get("pack")
    spec["pack"] = pack if isinstance(pack, str) and pack in effects.PACKS else ""
    src = raw.get("source")
    if isinstance(src, dict) and all(k in src for k in SOURCE_KEYS):
        spec["source"] = {k: src[k] for k in SOURCE_KEYS}
    return spec, warnings


def effective_pack(spec: dict) -> str:
    """The pack to show as selected: the one the user picked, but only while the presets still match it.
    Ticking/unticking presets by hand makes the pack label fall back to the placeholder (and it comes
    back if the presets are put back to match)."""
    pack = spec.get("pack") or ""
    if pack in effects.PACKS and set(spec.get("presets") or []) == set(effects.normalize([pack])[0]):
        return pack
    return ""


def is_default(spec: dict) -> bool:
    d = default_spec()
    return (list(spec.get("presets") or []) == d["presets"]
            and not _prune_params(spec.get("params") or {})
            and abs(_num(spec.get("speed"), 1.0) - 1.0) < 1e-9
            and bool(spec.get("use_overlay", True)))


def _normalize(spec: dict) -> None:
    spec["presets"], _ = effects.normalize(spec["presets"])


EFFECTS = Schema(suffix=".effects.json", version=SPEC_VERSION, editable=EDITABLE, default=default_spec,
                 sanitize=sanitize, is_default=is_default, normalize=_normalize)


def read_spec(video: str) -> tuple[dict, list[str]]:
    """Missing file -> default. Unreadable or newer-version file -> moved to .bak, default, warning."""
    return read_sidecar(video, EFFECTS)


def write_spec(video: str, spec: dict) -> None:
    """Atomic write; a default spec removes the sidecar instead of writing an empty one."""
    write_sidecar(video, spec, EFFECTS)


AUDIO_PRESETS = ("voice", "loudnorm", "mute")


def validate(spec: dict, current: dict, overlay_fx: list[dict], has_audio: bool) -> list[Issue]:
    """Spec vs the video actually selected. Nothing is changed or dropped silently: issues are shown."""
    issues = source_changed(spec, current)
    for i in issues:
        if i.kind == "resolution_changed":
            i.message += " Posisi efek Overlay (piksel) mungkin salah."
    if not has_audio and any(p in AUDIO_PRESETS for p in spec.get("presets") or []):
        issues.append(Issue("no_audio", "Video tanpa audio; preset audio (voice/loudnorm/mute) diabaikan."))
    dur = current.get("duration") or 0.0
    for i, fx in enumerate(overlay_fx):
        problem = effect_problem(fx)
        if problem:
            issues.append(Issue("incomplete", f"Efek Overlay #{i + 1} ({fx.get('type')}): {problem}; "
                                              "dilewati saat render.", i))
            continue
        start = _t(fx.get("start"), 0.0)
        if dur > 0 and start >= dur:
            issues.append(Issue("effect_out_of_range",
                                f"Efek Overlay #{i + 1} ({fx.get('type')}) mulai di {start:g}s, "
                                f"setelah video berakhir ({dur:.1f}s).", i))
    return issues


class EffectsSession(SpecSession):
    """Everything the Effects panel needs that is not a widget (see core/sidecar.SpecSession)."""

    def __init__(self, schedule, cancel, *, reader=read_spec, writer=write_spec, overlay_loader=load_overlay):
        super().__init__(EFFECTS, schedule, cancel, reader=reader, writer=writer)
        self._overlay = overlay_loader

    def revalidate(self) -> list[Issue]:
        if self.video is None or self.current is None:
            self.issues = []
        else:
            overlay = self._overlay(self.video) if self.spec["use_overlay"] else []
            self.issues = validate(self.spec, self.current, overlay, self.has_audio)
        return self.issues

    def snapshot(self) -> dict | None:
        """Immutable inputs for one render, taken at click time. Overlay effects are read fresh."""
        if self.video is None:
            return None
        return {
            "video": self.video,
            "presets": list(self.spec["presets"]),
            "params": copy.deepcopy(self.spec["params"]),
            "speed": self.spec["speed"],
            "overlay_effects": usable_overlay(self._overlay(self.video)) if self.spec["use_overlay"] else [],
        }
