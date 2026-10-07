"""Chạy frida script (unpin) spawn-attach vào app mục tiêu."""
import subprocess
from pathlib import Path

from ..errors import HarnessError

_REPO_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts" / "frida"


def ensure_scripts() -> dict:
    _REPO_SCRIPTS.mkdir(parents=True, exist_ok=True)
    return {p.stem: p for p in _REPO_SCRIPTS.glob("*.js")}


def unpin_cmd(package: str, script: Path) -> list:
    return ["frida", "-U", "-f", package, "-l", str(script), "--no-pause"]


def run_unpin(package: str, script: Path | None, runner=None) -> tuple:
    if script is None:
        scripts = ensure_scripts()
        if "unpin" not in scripts:
            raise HarnessError("khong thay scripts/frida/unpin.js",
                                hint="vendor unpin.js vao scripts/frida/")
        script = scripts["unpin"]
    r = (runner or subprocess.run)(unpin_cmd(package, script), timeout=300)
    code, out = (r.returncode, r.stdout) if hasattr(r, "returncode") else r
    return code, out or ""
