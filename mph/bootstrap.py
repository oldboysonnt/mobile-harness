"""Bootstrap công cụ ngoài: cmdline-tools, system image, AVD.

Ruling (2026-10-07): avdmanager hỏi "custom hardware profile?" — truyền
input='no\\n' để không treo khi chạy thật; runner giả trong test chấp nhận **kw.
"""
import os
import subprocess
import urllib.request
import zipfile
from pathlib import Path

from .errors import HarnessError

# Pin bản cmdline-tools đã biết ổn định; override qua tham số khi cần
CMDLINE_TOOLS_URL = (
    "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
)


def ensure_cmdline_tools(
    sdk: Path,
    cache: Path,
    fetch=urllib.request.urlretrieve,
    unzip=None,
) -> Path:
    """Đảm bảo sdk/cmdline-tools/latest tồn tại; idempotent."""
    dest = Path(sdk) / "cmdline-tools" / "latest"
    marker = dest / "bin" / "sdkmanager.bat"
    if marker.exists():
        return dest
    cache.mkdir(parents=True, exist_ok=True)
    z = cache / "cmdline-tools.zip"
    if not z.exists():
        fetch(CMDLINE_TOOLS_URL, z)
    Path(sdk).mkdir(parents=True, exist_ok=True)
    tmp_extract = Path(sdk) / "_cmdline_tmp"
    if unzip:
        unzip(z, tmp_extract)
    else:
        with zipfile.ZipFile(z) as zf:
            zf.extractall(tmp_extract)
    inner = tmp_extract / "cmdline-tools"
    if dest.exists():
        raise HarnessError(
            "cmdline-tools/latest da ton tai", hint="xoa thu muc va chay lai"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    inner.rename(dest)
    import shutil

    shutil.rmtree(tmp_extract, ignore_errors=True)
    return dest


def _sdkmanager(sdk: Path) -> str:
    return str(Path(sdk) / "cmdline-tools" / "latest" / "bin" / "sdkmanager.bat")


def install_image(sdk: Path, image: str, runner=subprocess.run) -> None:
    """Chấp nhận license rồi cài system image qua sdkmanager."""
    lic = runner(
        [_sdkmanager(sdk), "--sdk_root=" + str(sdk), "--licenses"],
        input="y\n" * 20,
        text=True,
        timeout=600,
    )
    ins = runner(
        [_sdkmanager(sdk), "--sdk_root=" + str(sdk), image],
        input="y\n" * 5,
        text=True,
        timeout=3600,
    )
    if getattr(ins, "returncode", ins[0] if isinstance(ins, tuple) else 1) != 0:
        raise HarnessError(
            "cai system image that bai",
            hint=f"sdkmanager output: {getattr(ins, 'stdout', ins)}"[-500:],
        )


def create_avd(sdk: Path, name: str, image: str, runner=subprocess.run,
               force: bool = False) -> None:
    """Tạo AVD workhorse; BỎ QUA nếu đã tồn tại (bảo vệ AVD đã root/snapshot)."""
    ini = Path.home() / ".android" / "avd" / f"{name}.ini"
    if ini.exists() and not force:
        return
    avdm = str(Path(sdk) / "cmdline-tools" / "latest" / "bin" / "avdmanager.bat")
    r = runner(
        [avdm, "create", "avd", "-n", name, "-k", image, "-d", "pixel_6", "--force"],
        input="no\n",
        text=True,
        timeout=120,
    )
    code = getattr(r, "returncode", r[0] if isinstance(r, tuple) else 1)
    if code != 0:
        err = getattr(r, "stderr", r)
        raise HarnessError("tao AVD that bai", hint=f"avdmanager: {str(err)[-500:]}")
