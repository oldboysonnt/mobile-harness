"""Root AVD bằng rootAVD (Magisk vào ramdisk của emulator)."""
import os
import subprocess
from pathlib import Path

from ..errors import HarnessError


def build_root_cmd(git_bash: Path, rootavd_dir: Path, avd_home: Path) -> list[str]:
    return [str(git_bash), str(Path(rootavd_dir) / "rootAVD.sh"), str(avd_home)]


def root_via_rootavd(cfg, rootavd_dir: Path, runner=None) -> bool:
    """Patch Magisk; True khi 'All done'/'already'. Truyền runner để test."""
    avd_name = getattr(cfg, "avd_name", "mph_avd")
    git_bash = getattr(cfg, "git_bash", "bash")
    sdk = getattr(cfg, "sdk", None)
    avd_home = Path.home() / ".android" / "avd" / f"{avd_name}.avd"
    if runner is None and not avd_home.exists():
        raise HarnessError(f"AVD khong ton tai: {avd_home}",
                            hint="chay mph setup run truoc")
    cmd = build_root_cmd(Path(git_bash), rootavd_dir, avd_home)
    env = {**dict(os.environ)}
    if sdk is not None:
        env["ANDROID_HOME"] = str(sdk)
    code, out, err = (runner or _run)(cmd, env=env, timeout=900)
    if "All done" in out or "already" in out.lower():
        return True
    raise HarnessError("rootAVD that bai", hint=(err[-400:] or out[-400:]))


def _run(cmd, env=None, timeout=None):
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def magisk_present(adb) -> bool:
    r = adb.run("shell", "su", "-v")
    return r.ok and ":" in r.out
