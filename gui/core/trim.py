import os
import subprocess
import sys
from dataclasses import dataclass, field

from core.cut import parse_time
from core.paths import ffmpeg_path

_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _run(cmd, log):
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
        creationflags=_CREATE_NO_WINDOW,
    )
    for line in proc.stdout:
        log(line.rstrip())
    proc.wait()
    return proc.returncode == 0


def trim_video(input_path: str, start: str, end: str, output_path: str, log=print,
                preset: str = "fast", crf: int = 18) -> bool:
    log(f"[Trim] Trimming {start} - {end}...")
    ok = _run(
        [
            ffmpeg_path(), "-y", "-ss", start, "-to", end, "-i", input_path,
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ],
        log,
    )
    log("[Trim] Done." if ok else "[Trim] Failed.")
    return ok


def trim_audio(input_path: str, start: str, end: str, output_path: str, encode_mp3: bool, log=print) -> bool:
    log(f"[Trim] Trimming {start} - {end}...")
    codec_args = ["-c:a", "libmp3lame", "-b:a", "192k"] if encode_mp3 else ["-c:a", "aac", "-b:a", "192k"]
    ok = _run(
        [
            ffmpeg_path(), "-y", "-ss", start, "-to", end, "-i", input_path,
            "-vn", *codec_args,
            output_path,
        ],
        log,
    )
    log("[Trim] Done." if ok else "[Trim] Failed.")
    return ok


def row_problem(start: str, end: str) -> str | None:
    """Why a (start, end) row can't be trimmed, or None if it can.
    A completely empty row is reported as "empty" (an unused row, harmless); anything else is a
    mistake worth stopping for."""
    start, end = start.strip(), end.strip()
    if not start and not end:
        return "empty"
    if not start:
        return "Start is empty"
    if not end:
        return "End is empty"
    try:
        s, e = parse_time(start), parse_time(end)
    except ValueError:
        return f"invalid time ({start} -> {end})"
    if e <= s:
        return f"End ({end}) is not after Start ({start})"
    return None


def incomplete_rows(segments: list[tuple[str, str]]) -> list[tuple[int, str]]:
    """Rows (1-based) that are half-filled or invalid; unused empty rows are not included."""
    out = []
    for i, (start, end) in enumerate(segments, start=1):
        problem = row_problem(start, end)
        if problem and problem != "empty":
            out.append((i, problem))
    return out


@dataclass
class BulkResult:
    created: list[int] = field(default_factory=list)          # row numbers
    skipped: list[tuple[int, str]] = field(default_factory=list)  # (row, reason)
    failed: list[int] = field(default_factory=list)           # ffmpeg errors

    def summary(self, total: int) -> str:
        parts = [f"{len(self.created)} created"]
        if self.skipped:
            parts.append("skipped " + ", ".join(f"row {r}: {why}" for r, why in self.skipped))
        if self.failed:
            parts.append("ffmpeg failed on row " + ", ".join(str(r) for r in self.failed))
        return f"{total} rows: " + "; ".join(parts)


def bulk_trim(input_path: str, segments: list[tuple[str, str]], output_dir: str,
              is_video: bool, encode_mp3: bool = False, log=print,
              preset: str = "fast", crf: int = 18) -> BulkResult:
    """Runs one trim per (start, end) segment. Clip files are named after their row number
    (`clip_<row>`), so a skipped row leaves a visible gap, and every skip is logged with its reason."""
    ext = ".mp4" if is_video else (".mp3" if encode_mp3 else ".m4a")
    result = BulkResult()
    for i, (start, end) in enumerate(segments, start=1):
        problem = row_problem(start, end)
        if problem:
            result.skipped.append((i, problem))
            log(f"[Trim] Row {i} skipped: {problem}.")
            continue
        output_path = os.path.join(output_dir, f"clip_{i}{ext}")
        if is_video:
            ok = trim_video(input_path, start, end, output_path, log=log, preset=preset, crf=crf)
        else:
            ok = trim_audio(input_path, start, end, output_path, encode_mp3, log=log)
        (result.created if ok else result.failed).append(i)
    log(f"[Trim] Done. {result.summary(len(segments))}")
    return result
