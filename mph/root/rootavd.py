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
    """Patch Magisk vào ramdisk; True khi 'All done'/'already'.

    rootAVD muốn tham số là đường dẫn TƯƠNG ĐỐI từ ANDROID_HOME (dạng
    system-images/.../ramdisk.img) — chạy với cwd=ANDROID_HOME.
    """
    git_bash = Path(getattr(cfg, "git_bash", "bash"))
    sdk = Path(getattr(cfg, "sdk", "."))
    parts = str(getattr(cfg, "image", "")).split(";")
    rel = "/".join(parts[1:]) if parts[0] == "system-images" else None
    if rel is None:
        raise HarnessError("cfg.image khong phai system-images",
                            hint=str(getattr(cfg, "image", "")))
    cmd = [git_bash.as_posix(), str(Path(rootavd_dir) / "rootAVD.sh"),
           f"system-images/{rel}/ramdisk.img"]
    env = {**dict(os.environ), "ANDROID_HOME": sdk.as_posix(),
           # Git Bash mangle /data/... thành C:/Program Files/Git/data/...
           "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"}
    code, out, err = (runner or _run)(cmd, env=env, timeout=900, cwd=str(sdk))
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
