import json
import os


def _path() -> str:
    # VFAST_SETTINGS lets tests point at a scratch file instead of the user's real settings.
    override = os.environ.get("VFAST_SETTINGS")
    if override:
        return override
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "vfast", "settings.json")


def _load() -> dict:
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get(key: str, default=None):
    return _load().get(key, default)


def set(key: str, value) -> None:
    """Persist one UI preference; failures are ignored (a preference is never worth an error)."""
    data = _load()
    data[key] = value
    try:
        os.makedirs(os.path.dirname(_path()), exist_ok=True)
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass
