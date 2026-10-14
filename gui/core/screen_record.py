import re
import subprocess
import sys

from core.paths import ffmpeg_path

_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def list_microphones() -> list[str]:
    """Enumerate dshow audio devices by parsing ffmpeg -list_devices stderr."""
    proc = subprocess.run(
        [ffmpeg_path(), "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_CREATE_NO_WINDOW,
    )
    devices = []
    for line in proc.stderr.splitlines():
        match = re.search(r'"(.+)"\s+\(audio\)\s*$', line.strip())
        if match:
            devices.append(match.group(1))
    return devices


class ScreenRecorder:
    """Start/stop wrapper around an ffmpeg gdigrab+dshow capture process."""

    def __init__(self):
        self._proc: subprocess.Popen | None = None

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self, mic_name: str, output_path: str, log=print):
        if self.running:
            return
        log("[ScreenRecord] Starting recording...")
        self._proc = subprocess.Popen(
            [
                ffmpeg_path(), "-y",
                "-f", "gdigrab", "-framerate", "30", "-i", "desktop",
                "-f", "dshow", "-i", f"audio={mic_name}",
                "-map", "0:v", "-map", "1:a",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                output_path,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW,
        )

    def stop(self, log=print):
        if not self.running:
            return
        log("[ScreenRecord] Stopping...")
        try:
            self._proc.communicate(input=b"q", timeout=5)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        log("[ScreenRecord] Stopped.")
        self._proc = None
