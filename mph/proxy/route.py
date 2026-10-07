"""Route traffic device qua proxy: adb reverse + global http_proxy."""
from ..errors import HarnessError


def proxy_on(adb, port: int) -> None:
    """Bật: adb reverse (remove + re-add — rule cũ chết ngầm sau adbd
    restart) + system http_proxy trỏ 127.0.0.1:port."""
    adb.run("reverse", f"--remove tcp:{port}")  # bỏ qua lỗi khi chưa có rule
    r = adb.run("reverse", f"tcp:{port}", f"tcp:{port}")
    if not r.ok:
        raise HarnessError("adb reverse that bai", hint=r.err)
    adb.run("shell", "settings", "put", "global", "http_proxy",
            f"127.0.0.1:{port}")


def proxy_off(adb) -> None:
    """Dọn sạch cả hai đường (idempotent)."""
    adb.run("shell", "settings", "put", "global", "http_proxy", ":0")
    adb.run("reverse", "--remove-all")
