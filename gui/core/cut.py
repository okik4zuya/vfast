import subprocess
import sys

from core.paths import ffmpeg_path
from core.media import has_audio_stream

_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def parse_time(t: str) -> float:
    """HH:MM:SS[.mmm] -> seconds (float)."""
    t = t.strip()
    if not t:
        raise ValueError("empty time")
    main, _, frac = t.partition(".")
    parts = main.split(":")
    parts = [int(p) for p in parts]
    while len(parts) < 3:
        parts.insert(0, 0)
    hh, mm, ss = parts[-3:]
    seconds = hh * 3600 + mm * 60 + ss
    if frac:
        seconds += float(f"0.{frac}")
    return float(seconds)


def cut_media(input_path: str, remove_ranges: list[tuple[str, str]], total_duration: float,
              output_path: str, is_video: bool, log=print,
              preset: str = "fast", crf: int = 18) -> bool:
    """Keeps everything NOT covered by remove_ranges (complement cut)."""
    # Normalize + sort ranges by start, drop unparsable/empty rows.
    parsed = []
    for start, end in remove_ranges:
        if not start or not end:
            continue
        try:
            s, e = parse_time(start), parse_time(end)
        except ValueError:
            continue
        if e > s:
            parsed.append((s, e))
    parsed.sort(key=lambda r: r[0])

    has_audio = has_audio_stream(input_path) if is_video else True

    segments = []
    prev = 0.0
    idx = 0
    for start, end in parsed:
        if start > prev:
            idx += 1
            v_label = f"v{idx}"
            a_label = f"a{idx}"
            if is_video:
                segments.append(f"[0:v]trim=start={prev}:end={start},setpts=PTS-STARTPTS[{v_label}]")
            if has_audio:
                segments.append(f"[0:a]atrim=start={prev}:end={start},asetpts=PTS-STARTPTS[{a_label}]")
        prev = max(prev, end)

    if prev < total_duration:
        idx += 1
        v_label = f"v{idx}"
        a_label = f"a{idx}"
        if is_video:
            segments.append(f"[0:v]trim=start={prev}:end={total_duration},setpts=PTS-STARTPTS[{v_label}]")
        if has_audio:
            segments.append(f"[0:a]atrim=start={prev}:end={total_duration},asetpts=PTS-STARTPTS[{a_label}]")

    if idx == 0:
        log("[Cut] No valid segments to keep (whole file is removed?).")
        return False

    concat_parts = []
    for i in range(1, idx + 1):
        if is_video:
            concat_parts.append(f"[v{i}]")
        if has_audio:
            concat_parts.append(f"[a{i}]")

    v_flag = 1 if is_video else 0
    a_flag = 1 if has_audio else 0
    out_labels = []
    if is_video:
        out_labels.append("[outv]")
    if has_audio:
        out_labels.append("[outa]")

    filter_complex = ";".join(segments) + ";" + "".join(concat_parts) + \
        f"concat=n={idx}:v={v_flag}:a={a_flag}" + "".join(out_labels)

    cmd = [ffmpeg_path(), "-y", "-i", input_path, "-filter_complex", filter_complex]
    if is_video:
        cmd += ["-map", "[outv]"]
        if has_audio:
            cmd += ["-map", "[outa]"]
        cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf)]
        if has_audio:
            cmd += ["-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-map", "[outa]", "-c:a", "libmp3lame", "-b:a", "192k"]
    cmd.append(output_path)

    log("[Cut] Cutting...")
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

    ok = proc.returncode == 0
    log("[Cut] Done." if ok else "[Cut] Failed.")
    return ok
