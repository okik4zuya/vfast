import os
import sys


def _version_file() -> str:
    # Frozen: vfast.spec bundles gui/VERSION at the root of the extraction dir.
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "VERSION")


def _read() -> str:
    try:
        with open(_version_file(), encoding="utf-8") as f:
            return f.read().strip() or "unknown"
    except OSError:
        return "unknown"


APP_VERSION = _read()
