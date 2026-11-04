import os
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


_REC_SUFFIX = ".rec.mkv"


def remux_to_mp4(src: str, dst: str, log=print) -> bool:
    """Stream-copy a recording into MP4. Deletes src only if the remux succeeded."""
    proc = subprocess.run(
        [ffmpeg_path(), "-y", "-i", src, "-c", "copy", "-movflags", "+faststart", dst],
        capture_output=True,
        creationflags=_CREATE_NO_WINDOW,
    )
    if proc.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0:
        os.remove(src)
        return True
    log(f"[ScreenRecord] Remux failed; raw recording kept at {src}")
    return False


def find_unfinished(folder: str) -> list[str]:
    """Raw .rec.mkv files left behind by a crash / power loss."""
    if not folder or not os.path.isdir(folder):
        return []
    return [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(_REC_SUFFIX)]


def recover_unfinished(folder: str, log=print, exclude: str | None = None) -> list[str]:
    """Remux leftover raw recordings to MP4; returns the MP4 paths produced.

    `exclude` is the raw file of a recording in progress, which must be left alone.
    """
    recovered = []
    for src in find_unfinished(folder):
        if exclude and os.path.normcase(src) == os.path.normcase(exclude):
            continue
        dst = src[: -len(_REC_SUFFIX)] + ".mp4"
        if os.path.exists(dst):
            dst = src[: -len(_REC_SUFFIX)] + "_recovered.mp4"
        log(f"[ScreenRecord] Recovering unfinished recording: {os.path.basename(src)}")
        if remux_to_mp4(src, dst, log):
            recovered.append(dst)
    return recovered


class ScreenRecorder:
    """Start/stop wrapper around an ffmpeg gdigrab+dshow capture process.

    Records to a Matroska file, which stays playable up to the last written data
    if the machine dies mid-recording (MP4 would lose its index and be unplayable),
    then remuxes to the requested MP4 on a clean stop.
    """

    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._log_file = None
        self._raw_path: str | None = None
        self._output_path: str | None = None

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self, mic_name: str, output_path: str, log=print):
        if self.running:
            return
        log("[ScreenRecord] Starting recording...")
        self._output_path = output_path
        self._raw_path = os.path.splitext(output_path)[0] + _REC_SUFFIX
        # ffmpeg's stderr goes to a log next to the output so dropped frames /
        # buffer warnings can be diagnosed after the fact.
        log_path = os.path.splitext(output_path)[0] + ".ffmpeg.log"
        self._log_file = open(log_path, "wb")
        log(f"[ScreenRecord] ffmpeg log: {log_path}")
        # Wallclock timestamps give video and audio a shared time base, so a slow
        # dshow init no longer shifts one stream relative to the other.
        self._proc = subprocess.Popen(
            [
                ffmpeg_path(), "-y",
                "-use_wallclock_as_timestamps", "1", "-thread_queue_size", "1024",
                "-f", "gdigrab", "-framerate", "30", "-i", "desktop",
                "-use_wallclock_as_timestamps", "1", "-thread_queue_size", "1024",
                "-f", "dshow", "-i", f"audio={mic_name}",
                "-map", "0:v", "-map", "1:a",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-fps_mode", "cfr", "-r", "30",
                "-c:a", "aac", "-b:a", "192k",
                "-af", "aresample=async=1:first_pts=0",
                "-pix_fmt", "yuv420p",
                self._raw_path,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=self._log_file,
            creationflags=_CREATE_NO_WINDOW,
        )

    def stop(self, log=print):
        if not self.running:
            return
        log("[ScreenRecord] Stopping...")
        try:
            self._proc.communicate(input=b"q", timeout=30)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None
        self._proc = None
        log("[ScreenRecord] Stopped. Finalizing MP4...")
        if os.path.exists(self._raw_path):
            remux_to_mp4(self._raw_path, self._output_path, log)
