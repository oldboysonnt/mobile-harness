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


def avd_serial(avd_name: str | None = None, devices=None,
               name_of=None) -> str | None:
    """Serial emulator khớp tên AVD, state 'device'; None nếu mơ hồ."""
    list_devices = devices or Adb.devices
    get_name = name_of or _emu_avd_name
    online = [s for s, st in list_devices()
              if s.startswith("emulator-") and st == "device"]
    if avd_name is None:
        return online[0] if online else None
    unknown = []
    for s in online:
        nm = get_name(s)
        if nm == avd_name:
            return s
        if nm is None:
            unknown.append(s)
    if len(online) == 1 and unknown:
        return online[0]  # không xác minh được tên + chỉ 1 emulator → chấp nhận
    return None


def _emu_avd_name(serial: str) -> str | None:
    r = Adb(serial=serial).run("emu", "avd", "name", timeout=15)
    if not r.ok:
        return None
    first = r.out.strip().splitlines()[0].strip() if r.out.strip() else ""
    return first or None


def wait_booted(serial: str, adb: Adb, timeout: float = 300) -> bool:
    """Đợi sys.boot_completed == 1."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = adb.run("shell", "getprop", "sys.boot_completed", timeout=15)
        if r.ok and r.out.strip() == "1":
            return True
        time.sleep(3)
    return False


def wait_serial(timeout: float = 120, avd_name: str | None = None, devices=None,
                name_of=None, sleeper=time.sleep) -> str | None:
    """Đợi emulator đích đăng ký vào adb (theo tên AVD nếu có)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = avd_serial(avd_name, devices=devices, name_of=name_of)
        if s:
            return s
        sleeper(2)
    return None
