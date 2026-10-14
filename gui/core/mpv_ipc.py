import json
import time
from typing import Optional


def _open_pipe(pipe_name: str, deadline: float):
    """Retry until deadline — covers the brief window after Popen() before
    mpv has bound --input-ipc-server."""
    last_exc = None
    while time.monotonic() < deadline:
        try:
            return open(pipe_name, "r+b", buffering=0)
        except OSError as e:
            last_exc = e
            time.sleep(0.1)
    raise last_exc or TimeoutError(f"mpv IPC pipe not available: {pipe_name}")


def send_command(pipe_name: str, command: list, timeout: float = 1.5) -> Optional[dict]:
    """Send one JSON IPC command, read one JSON response line, close.
    Returns parsed dict or None on failure/timeout. MUST be called off the
    Tk main thread — the underlying pipe read has no OS-level timeout."""
    deadline = time.monotonic() + timeout
    try:
        with _open_pipe(pipe_name, deadline) as pipe:
            pipe.write(json.dumps({"command": command}).encode("utf-8") + b"\n")
            buf = b""
            while time.monotonic() < deadline:
                chunk = pipe.read(4096)
                if not chunk:
                    break
                buf += chunk
                if b"\n" in buf:
                    line, _, _ = buf.partition(b"\n")
                    return json.loads(line.decode("utf-8"))
            return None
    except (OSError, TimeoutError, ValueError):
        return None


def query_property(pipe_name: str, prop: str, timeout: float = 1.5) -> Optional[float]:
    resp = send_command(pipe_name, ["get_property", prop], timeout=timeout)
    if resp and resp.get("error") == "success":
        return resp.get("data")
    return None
