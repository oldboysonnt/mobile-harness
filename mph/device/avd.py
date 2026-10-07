"""Quản lý AVD workhorse: boot, dò serial, đợi boot xong."""
import subprocess
import time
from pathlib import Path

from ..errors import HarnessError
from .adb import Adb


def avd_boot(sdk: Path, name: str, runner_popen=subprocess.Popen) -> None:
    """Boot AVD nếu chưa có emulator nào đang chạy."""
    emu = Path(sdk) / "emulator" / "emulator.exe"
    if not emu.exists():
        raise HarnessError(
            "khong co emulator.exe", hint="chay sdkmanager de cai 'emulator'"
        )
    if avd_serial():
        return
    runner_popen(
        [str(emu), "-avd", name, "-no-snapshot-load", "-no-boot-anim"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def avd_serial() -> str | None:
    """Serial emulator-XXXX đầu tiên đang online."""
    for serial, _state in Adb.devices():
        if serial.startswith("emulator-"):
            return serial
    return None


def wait_booted(serial: str, adb: Adb, timeout: float = 300) -> bool:
    """Đợi sys.boot_completed == 1."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = adb.run("shell", "getprop", "sys.boot_completed", timeout=15)
        if r.ok and r.out.strip() == "1":
            return True
        time.sleep(3)
    return False
