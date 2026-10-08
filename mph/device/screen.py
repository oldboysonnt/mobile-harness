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


_META = set("$;|&<>()`\\%'\"")

def type_text(adb, s: str) -> None:
    if any(ord(ch) < 32 or ch in _META for ch in s):
        raise HarnessError("type_text ky tu khong ho tro (shell metachar)",
                            hint="chi ASCII in duoc, khong $;|&<>()`\\% ' \"")
    adb.run("shell", "input", "text", s.replace(" ", "%s"))


def key(adb, keycode: str) -> None:
    import re as _r
    if not _r.fullmatch(r"[A-Za-z0-9_]+", keycode):
        raise HarnessError("keycode khong hop le",
                            hint=f"chi [A-Za-z0-9_], nhan: {keycode!r}")
    adb.run("shell", "input", "keyevent", keycode)


# --- screenshot + ui dump (Task 2) ---
import re as _re
from pathlib import Path

_PNG = b"\x89PNG"


def _screencap_raw(adb) -> tuple[int, bytes]:
    return adb.run_raw("exec-out", "screencap", "-p", timeout=30)


def screenshot(adb, dest: Path) -> dict:
    """Chụp PNG binary-safe + meta tọa độ (screen = kích thước thật)."""
    code, data = _screencap_raw(adb)
    if code != 0 or not data.startswith(_PNG):
        raise HarnessError("screencap that bai / khong phai PNG",
                            hint=f"code={code} bytes={len(data)}")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return {"path": str(dest), "screen": list(wm_size(adb)),
            "png_bytes": len(data)}


def ui_dump(adb, dest: Path) -> Path:
    # xóa XML cũ trên device — dump fail thường để lại file của màn TRƯỚC
    adb.run("shell", "rm", "-f", "/sdcard/ui.xml")
    r = adb.run("shell", "uiautomator", "dump", "/sdcard/ui.xml", timeout=30)
    if not r.ok or "dumped" not in (r.out or ""):
        raise HarnessError("uiautomator dump that bai (khong sinh file moi)",
                            hint=(r.out or r.err or "")[:200])
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    p = adb.run("pull", "/sdcard/ui.xml", str(dest), timeout=30)
    if not p.ok or not dest.exists():
        raise HarnessError("pull ui.xml that bai", hint=p.err)
    return dest


_BOUNDS_ATTR_RE = _re.compile(
    r'bounds="\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]"')


def find_bounds(xml: Path, text: str) -> tuple[int, int] | None:
    """Center của node đầu có text khớp chính xác.

    Chỉ đọc bounds trong ATTR bounds="..." — bounds-like string trong
    content-desc/text khác không được dùng (anti wrong-tap).
    """
    if not text:
        return None
    raw = Path(xml).read_text(encoding="utf-8", errors="replace")
    for m in _re.finditer(r"<node[^>]*>", raw):
        node = m.group(0)
        if f'text="{text}"' in node:
            b = _BOUNDS_ATTR_RE.search(node)
            if b:
                x1, y1, x2, y2 = map(int, b.groups())
                return (x1 + x2) // 2, (y1 + y2) // 2
    return None
