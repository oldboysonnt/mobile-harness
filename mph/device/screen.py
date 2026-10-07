"""Điều khiển màn hình: tọa độ theo màn hình thật (wm size)."""
from ..errors import HarnessError


def wm_size(adb) -> tuple[int, int]:
    """(w, h) — Override size (nếu có) ưu tiên hơn Physical."""
    r = adb.run("shell", "wm", "size")
    phys = over = None
    for line in (r.out or "").splitlines():
        if line.startswith("Override size:"):
            over = line.split(":", 1)[1].strip()
        elif line.startswith("Physical size:"):
            phys = line.split(":", 1)[1].strip()
    raw = over or phys
    if not raw or "x" not in raw:
        raise HarnessError("khong doc duoc wm size", hint=(r.out or "")[:100])
    w, h = raw.lower().split("x", 1)
    return int(w), int(h)


def tap(adb, x: int, y: int) -> None:
    adb.run("shell", "input", "tap", str(int(x)), str(int(y)))


def swipe(adb, x1: int, y1: int, x2: int, y2: int, ms: int = 300) -> None:
    adb.run("shell", "input", "swipe",
            str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(ms)))


def type_text(adb, s: str) -> None:
    if any(ord(ch) < 32 or ch == '"' for ch in s):
        raise HarnessError("type_text ky tu khong ho tro",
                            hint="chi ASCII in duoc; dung key() cho dieu khien")
    adb.run("shell", "input", "text", s.replace(" ", "%s"))


def key(adb, keycode: str) -> None:
    adb.run("shell", "input", "keyevent", keycode)
