"""Chạy frida script (unpin) spawn-attach vào app mục tiêu."""
import subprocess
from pathlib import Path

from ..errors import HarnessError

_REPO_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts" / "frida"


def ensure_scripts() -> dict:
    _REPO_SCRIPTS.mkdir(parents=True, exist_ok=True)
    return {p.stem: p for p in _REPO_SCRIPTS.glob("*.js")}


def unpin_cmd(package: str, script: Path) -> list:
    # frida 17 CLI đã bỏ --no-pause (spawn tự resume khi có script)
    return ["frida", "-U", "-f", package, "-l", str(script)]


def run_unpin(package: str, script: Path | None, runner=None,
              timeout: int = 300) -> tuple:
    """Spawn-attach script vào package. frida CLI giữ session (REPL) sau khi
    script chạy — timeout được coi là thành công bình thường, không lỗi."""
    if script is None:
        scripts = ensure_scripts()
        if "unpin" not in scripts:
            raise HarnessError("khong thay scripts/frida/unpin.js",
                                hint="vendor unpin.js vao scripts/frida/")
        script = scripts["unpin"]
    try:
        r = (runner or subprocess.run)(unpin_cmd(package, script),
                                       timeout=timeout)
    except subprocess.TimeoutExpired:
        return 0, "session held (frida CLI giữ REPL — bình thường)"
    code, out = (r.returncode, r.stdout) if hasattr(r, "returncode") else r
    return code, out or ""
