"""Điều khiển Magisk: Zygisk, DenyList, cài module, ẩn dấu hiệu emulator."""
from pathlib import Path

from ..errors import HarnessError
from .rootavd import magisk_present

_GMS = "com.google.android.gms"

_EMU_PROPS = {
    "ro.kernel.qemu": "0",
    "ro.boot.qemu": "0",
    "ro.hardware": "radio",
    "ro.product.device": "walleye",
    "ro.product.board": "walleye",
    "ro.board.platform": "sdm845",
}


def require_magisk(adb) -> None:
    if not magisk_present(adb):
        raise HarnessError("Magisk chua san sang (su -v that bai)",
                            hint="chay: mph root install (rootAVD patch + boot lai)")


def zygisk_enable(adb) -> bool:
    require_magisk(adb)
    adb.run("shell", "su", "-c",
            'magisk --sqlite "INSERT OR REPLACE INTO settings (key,value)'
            " VALUES('zygisk',1)\"")
    adb.run("shell", "su", "-c", "resetprop persist.sys.zygisk 1")
    adb.run("shell", "su", "-c", "setprop persist.sys.zygisk 1")
    return True


def denylist_add(adb, package: str) -> bool:
    require_magisk(adb)
    adb.run("shell", "su", "-c", "magisk --denylist enable")
    for pkg in (_GMS, package):
        adb.run("shell", "su", "-c", f"magisk --denylist add {pkg}")
    return True


def denylist_status(adb) -> list:
    r = adb.run("shell", "su", "-c", "magisk --denylist ls")
    return [line.split()[0] for line in r.out.splitlines() if line.strip()]


def install_module(adb, zip_local: Path) -> bool:
    require_magisk(adb)
    remote = f"/data/local/tmp/{Path(zip_local).name}"
    p = adb.run("push", str(zip_local), remote)
    if not p.ok:
        raise HarnessError("push module zip that bai", hint=p.err)
    adb.run("shell", "su", "-c", f"magisk --install-module {remote}")
    return True


def hide_emu_props(adb) -> bool:
    """L5: xóa dấu hiệu qemu/goldfish khỏi system props (resetprop qua su)."""
    require_magisk(adb)
    for k, v in _EMU_PROPS.items():
        adb.run("shell", "su", "-c", f"resetprop {k} {v}")
    return True
