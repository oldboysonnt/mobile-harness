"""Điều khiển Magisk: Zygisk, DenyList, cài module, ẩn dấu hiệu emulator."""
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
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
    adb.su('magisk --sqlite "INSERT OR REPLACE INTO settings (key,value)'
           " VALUES('zygisk',1)\"")
    adb.su("resetprop persist.sys.zygisk 1")
    adb.su("setprop persist.sys.zygisk 1")
    return True


def denylist_add(adb, package: str) -> bool:
    require_magisk(adb)
    adb.su("magisk --denylist enable")
    for pkg in (_GMS, package):
        adb.su(f"magisk --denylist add {pkg}")
    return True


def denylist_status(adb) -> list:
    r = adb.su("magisk --denylist ls")
    return [line.split()[0] for line in r.out.splitlines() if line.strip()]


def install_module(adb, zip_local: Path) -> bool:
    """Cài module: push zip + `magisk --install-module`; nếu daemon báo
    'Incomplete Magisk install' (Magisk ramdisk cũ) thì fallback: giải nén
    zip trên host, copy vào CẢ modules_update lẫn modules (kích hoạt ngay)."""
    require_magisk(adb)
    remote = f"/data/local/tmp/{Path(zip_local).name}"
    p = adb.run("push", str(zip_local), remote)
    if not p.ok:
        raise HarnessError("push module zip that bai", hint=p.err)
    r = adb.su(f"magisk --install-module {remote}")
    if r.ok and "Incomplete" not in (r.out + r.err):
        return True
    if "Incomplete" not in (r.out + r.err):
        raise HarnessError(
            "magisk --install-module that bai",
            hint=(r.err or r.out)[-300:])
    _install_module_manual(adb, zip_local)
    return True


def _install_module_manual(adb, zip_local: Path) -> str:
    tmp = Path(tempfile.mkdtemp())
    try:
        try:
            with zipfile.ZipFile(zip_local) as zf:
                zf.extractall(tmp)
        except NotImplementedError:  # zip zstd — bsdtar đọc được
            subprocess.run(["tar", "-xf", str(zip_local), "-C", str(tmp)],
                           check=True, capture_output=True, timeout=300)
        try:
            prop = (tmp / "module.prop").read_text(encoding="utf-8",
                                                   errors="replace")
            mid = re.search(r"^id=(\S+)", prop, re.M).group(1)
        except (FileNotFoundError, AttributeError) as e:
            raise HarnessError(f"module.prop khong hop le: {zip_local.name}",
                               hint=str(e)) from e
        stage = f"/data/local/tmp/modstage-{mid}-{time.time_ns()}"
        adb.run("shell", "mkdir", "-p", stage)
        adb.run("push", str(tmp) + "/.", stage)
        # F1+F2: dọn dest, copy vào CẢ 2 nơi, tự dọn stage
        adb.su(
            f"mkdir -p /data/adb/modules_update/{mid} "
            f"&& cp -R {stage}/. /data/adb/modules_update/{mid}/ "
            f"&& mkdir -p /data/adb/modules/{mid} "
            f"&& cp -R {stage}/. /data/adb/modules/{mid}/ "
            f"&& chmod -R 755 /data/adb/modules/{mid} "
            f"&& rm -rf {stage}")
        return mid
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def hide_emu_props(adb) -> bool:
    """L5: xóa dấu hiệu qemu/goldfish khỏi system props (resetprop qua su)."""
    require_magisk(adb)
    for k, v in _EMU_PROPS.items():
        adb.su(f"resetprop {k} {v}")
    return True
