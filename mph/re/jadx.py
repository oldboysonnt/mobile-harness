"""Decompile APK bằng jadx CLI (idempotent)."""
import subprocess
from pathlib import Path

from ..errors import HarnessError


def decompile(apk: Path, out_dir: Path, jadx_bin: str = "jadx",
              runner=None) -> Path:
    """Skip khi out_dir/sources đã có; accept exit != 0 nếu sources sinh ra."""
    out_dir = Path(out_dir)
    if (out_dir / "sources").exists():
        return out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [jadx_bin, "-d", str(out_dir), "--deobf", "-j", "4", str(apk)]
    run = runner or subprocess.run
    r = run(cmd, timeout=1800)
    rc = r.returncode if hasattr(r, "returncode") else r[0]
    if rc != 0 and not (out_dir / "sources").exists():
        raise HarnessError("jadx decompile that bai",
                            hint=f"exit={rc} — thu jadx thu cong xem log")
    return out_dir
