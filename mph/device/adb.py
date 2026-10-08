"""ADB wrapper: serial-aware, retry khi lỗi tạm thời, parse danh sách device."""
import subprocess
import time
from dataclasses import dataclass
from typing import Callable

TRANSIENT = ("device offline", "device not found", "closed", "timeout")

BACKOFF = (0.5, 1.0, 2.0)


def _raw_run(cmd: list[str], timeout: float | None = None) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


@dataclass(frozen=True)
class AdbResult:
    """Kết quả một lệnh adb: ok = exit code 0."""

    ok: bool
    out: str
    err: str
    code: int


class Adb:
    """Chạy lệnh adb, tự thêm `-s serial` và retry lỗi tạm thời."""

    def __init__(
        self,
        serial: str | None = None,
        adb_path: str = "adb",
        retries: int = 4,
        runner: Callable = _raw_run,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.serial = serial
        self.adb_path = adb_path
        self.retries = retries
        self._run = runner
        self._sleep = sleeper

    def run(self, *args: str, timeout: float = 60, device: bool = True) -> AdbResult:
        """Chạy lệnh; 1 lần đầu + (retries-1) retry lỗi tạm thời, backoff 0.5/1/2."""
        cmd = (
            [self.adb_path]
            + (["-s", self.serial] if (self.serial and device) else [])
            + list(args)
        )
        last: AdbResult | None = None
        for attempt in range(self.retries):
            try:
                code, out, err = self._run(cmd, timeout=timeout)
            except subprocess.TimeoutExpired:
                code, out, err = 124, "", "timeout expired"  # transient → retry
            last = AdbResult(code == 0, out, err, code)
            if last.ok or not any(t in err.lower() for t in TRANSIENT):
                return last
            if attempt < self.retries - 1:
                self._sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
        assert last is not None
        return last

    def su(self, cmd: str, timeout: float = 60) -> "AdbResult":
        """Chạy lệnh với quyền root qua `su -c` — một arg duy nhất để
        adb shell không vỡ quoting khi cmd chứa khoảng trắng."""
        import shlex
        return self.run("shell", f"su -c {shlex.quote(cmd)}", timeout=timeout)

    def run_raw(self, *args: str, timeout: float = 60) -> tuple[int, bytes]:
        """Chạy adb nhận binary stdout (screencap PNG) — không text pipe."""
        cmd = ([self.adb_path]
               + (["-s", self.serial] if self.serial else []) + list(args))
        p = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout

    @staticmethod
    def devices(adb_path: str = "adb") -> list[tuple[str, str]]:
        """Trả [(serial, state)] từ `adb devices`."""
        _, out, _ = _raw_run([adb_path, "devices"])
        devs: list[tuple[str, str]] = []
        for line in out.splitlines()[1:]:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] not in ("attached", "detached"):
                devs.append((parts[0], parts[1]))
        return devs
