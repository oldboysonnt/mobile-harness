"""Root AVD bằng rootAVD (Magisk vào ramdisk của emulator)."""
import os
import subprocess
from pathlib import Path

from ..errors import HarnessError


def build_root_cmd(git_bash: Path, rootavd_dir: Path, ramdisk: Path) -> list[str]:
    return [str(git_bash), str(Path(rootavd_dir) / "rootAVD.sh"), ramdisk.as_posix()]


def _ramdisk_path(cfg) -> Path:
    """ramdisk.img của system-image ứng với cfg.image (API 34: ramdisk.img)."""
    parts = str(cfg.image).split(";")  # system-images;android-34;google_apis;x86_64
    rel = "/".join(parts[1:]) if parts[0] == "system-images" else None
    if rel is None:
        raise HarnessError("cfg.image khong phai system-images", hint=str(cfg.image))
    img_dir = Path(cfg.sdk) / "system-images" / rel
    for name in ("ramdisk.img", "init_boot.img"):
        c = img_dir / name
        if c.exists():
            return c
    raise HarnessError(f"khong thay ramdisk trong {img_dir}",
                        hint="chay mph setup run truoc")


def root_via_rootavd(cfg, rootavd_dir: Path, runner=None) -> bool:
    """Patch Magisk vào ramdisk; True khi 'All done'/'already'."""
    git_bash = getattr(cfg, "git_bash", "bash")
    sdk = getattr(cfg, "sdk", None)
    ramdisk = _ramdisk_path(cfg)
    cmd = build_root_cmd(Path(git_bash).as_posix(), Path(rootavd_dir), ramdisk)
    env = {**dict(os.environ)}
    if sdk is not None:
        env["ANDROID_HOME"] = str(sdk)
    code, out, err = (runner or _run)(cmd, env=env, timeout=900,
                                      cwd=str(rootavd_dir))
    if "All done" in out or "already" in out.lower():
        return True
    raise HarnessError("rootAVD that bai", hint=(err[-400:] or out[-400:]))


def _run(cmd, env=None, timeout=None, cwd=None):
    p = subprocess.run(cmd, capture_output=True, text=True, env=env,
                       timeout=timeout, cwd=cwd)
    return p.returncode, p.stdout, p.stderr


def magisk_present(adb) -> bool:
    r = adb.run("shell", "su", "-v")
    return r.ok and ":" in r.out
