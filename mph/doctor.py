"""Kiểm tra môi trường: mọi thành phần harness cần có mặt hay chưa."""
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import Config


def _default_exists(p) -> bool:
    return Path(p).exists()


@dataclass(frozen=True)
class Probes:
    """Các thăm dò tách biệt để test tiêm giả lập."""

    exists: Callable = _default_exists
    which: Callable = shutil.which
    devices: Callable = lambda: []


def check_env(cfg: Config, probes: Probes | None = None) -> list[tuple[str, bool, str]]:
    """Trả [(tên, ok, hint)] cho từng thành phần môi trường."""
    p = probes or Probes()
    rows: list[tuple[str, bool, str]] = [
        ("adb", p.which("adb") is not None,
         "cai dat platform-tools hoac them scrcpy vao PATH"),
        ("android-sdk", p.exists(cfg.sdk), f"dat ANDROID_HOME — khong thay {cfg.sdk}"),
        ("emulator", p.exists(Path(cfg.sdk) / "emulator" / "emulator.exe"),
         "sdkmanager 'emulator'"),
        ("burp", p.exists(cfg.burp_exe), "dat env BURP_PATH tro den jar/exe Burp"),
        ("git-bash", p.exists(cfg.git_bash), "cai Git for Windows"),
    ]
    devs = p.devices()
    rows.append(("device", len(devs) > 0, "mph avd boot de tao device"))
    return rows
