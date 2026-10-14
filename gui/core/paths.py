import os
import sys


def get_tool_dir() -> str:
    """Root of the vfast install: dev = repo root, frozen = folder holding the exe."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_bin_dir() -> str:
    """bin/ folder, resolving PyInstaller's onefile extraction dir when frozen."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        return os.path.join(base, "bin")
    return os.path.join(get_tool_dir(), "bin")


def ffmpeg_path() -> str:
    return os.path.join(get_bin_dir(), "ffmpeg.exe")


def ffprobe_path() -> str:
    return os.path.join(get_bin_dir(), "ffprobe.exe")


def mpv_path() -> str:
    return os.path.join(get_bin_dir(), "mpv.exe")


def rnnoise_model_path() -> str:
    return os.path.join(get_bin_dir(), "models", "rnnoise-general.rnnn")
