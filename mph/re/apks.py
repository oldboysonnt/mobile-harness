"""Quản lý APK trên device + layout workspace per-app."""
from pathlib import Path

from ..errors import HarnessError


def app_workspace(cfg, app: str) -> Path:
    ws = Path(cfg.workspace) / app
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def list_packages(adb) -> list:
    r = adb.run("shell", "pm", "list", "packages", "-3")
    pkgs = []
    for line in (r.out or "").splitlines():
        line = line.strip()
        if line.startswith("package:"):
            pkgs.append(line[len("package:"):])
    return pkgs


def pull_apk(adb, package: str, dest_dir: Path) -> Path:
    """Pull APK (ưu tiên base.apk khi app split) vào dest_dir/<pkg>.apk."""
    r = adb.run("shell", "pm", "path", package)
    paths = [line.replace("package:", "").strip()
             for line in (r.out or "").splitlines() if line.strip()]
    if not paths:
        raise HarnessError(f"khong thay package tren device: {package}",
                            hint="kiem tra pm list packages")
    src = next((p for p in paths if p.endswith("base.apk")), paths[0])
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{package}.apk"
    p = adb.run("pull", src, str(dest), timeout=300)
    if not p.ok:
        raise HarnessError("pull apk that bai", hint=p.err)
    return dest


def install_apk(adb, apk: Path) -> bool:
    r = adb.run("install", "-r", str(apk), timeout=300)
    if not r.ok:
        raise HarnessError("install apk that bai", hint=(r.out + r.err)[-300:])
    return True
