"""Frida server ẩn: StrongR/hluda, alias sạch, port tuỳ chọn."""
import re
import subprocess
import time
from pathlib import Path

from ..errors import HarnessError

BANNED = {"frida", "hluda", "gum", "gadget"}


def sanitize_alias(alias: str) -> str:
    a = re.sub(r"[^a-z0-9_.]", "", alias.lower()) or "sysmondd"
    if a in BANNED:
        a = a + "d"
    return a


def unpack_strongr(xz_path: Path, out_dir: Path) -> Path:
    """Giải nén frida-server .xz bằng lzma stdlib (GNU tar trên Git Bash
    không đọc được định dạng này)."""
    import lzma
    out = Path(out_dir) / "frida-server-bin"
    if out.exists():
        return out
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    try:
        data = lzma.decompress(Path(xz_path).read_bytes())
    except lzma.LZMAError as e:
        raise HarnessError("giai nen frida-server.xz that bai", hint=str(e)) from e
    out.write_bytes(data)
    return out


def _wait_frida_ps(adb, tries: int = 5, delay: float = 2.0) -> bool:
    for _ in range(tries):
        try:
            p = subprocess.run(["frida-ps", "-U"], capture_output=True,
                               text=True, timeout=15)
            if p.returncode == 0 and ("PID" in p.stdout or p.stdout.strip()):
                return True
        except OSError:
            pass
        time.sleep(delay)
    return False


def frida_start(adb, strongr_xz: Path, alias: str = "sysmondd",
                port: int = 27042, tools_dir=None) -> str:
    alias = sanitize_alias(alias)
    local = unpack_strongr(Path(strongr_xz),
                           Path(tools_dir) if tools_dir
                           else Path(strongr_xz).parent)
    remote = f"/data/local/tmp/{alias}"
    p = adb.run("push", str(local), remote)
    if not p.ok:
        raise HarnessError("push frida-server that bai", hint=p.err)
    adb.run("shell", "chmod", "755", remote)
    adb.run("shell", "su", "-c", f"{remote} -l 127.0.0.1:{port} >/dev/null 2>&1 &")
    if not _wait_frida_ps(adb):
        raise HarnessError(
            "frida-server khong phan hoi sau 10s",
            hint="kiem tra strongr version khop pip frida, xem adb logcat")
    return remote


def frida_stop(adb, alias: str) -> bool:
    adb.run("shell", "su", "-c", f"pkill -f {sanitize_alias(alias)}")
    return True
