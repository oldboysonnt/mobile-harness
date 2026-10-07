"""Quản lý AVD workhorse: boot, dò serial, đợi boot xong."""
import subprocess
import time
from pathlib import Path

from ..errors import HarnessError
from .adb import Adb


def avd_boot(sdk: Path, name: str, runner_popen=subprocess.Popen,
             log_path: Path | None = None) -> None:
    """Boot AVD nếu chưa có emulator nào đang chạy. Ghi log để chẩn đoán."""
    emu = Path(sdk) / "emulator" / "emulator.exe"
    if not emu.exists():
        raise HarnessError(
            "khong co emulator.exe", hint="chay sdkmanager de cai 'emulator'"
        )
    if avd_serial():
        return
    log_file = None
    if log_path is not None:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_path, "ab")  # noqa: SIM115 — sống suốt process
    runner_popen(
        [str(emu), "-avd", name, "-no-snapshot-load", "-no-boot-anim"],
        stdout=log_file if log_file else subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
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


def wait_serial(timeout: float = 120, devices=None, sleeper=time.sleep) -> str | None:
    """Đợi emulator đăng ký vào adb (poll danh sách device)."""
    list_devices = devices or Adb.devices
    deadline = time.time() + timeout
    while time.time() < deadline:
        for serial, _state in list_devices():
            if serial.startswith("emulator-"):
                return serial
        sleeper(2)
    return None
