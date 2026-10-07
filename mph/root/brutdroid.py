"""Vendor BrutDroid (pin SHA) — đường root thay thế experimental."""
import subprocess
from pathlib import Path

from ..errors import HarnessError


def _rev_parse(dest: Path):
    return subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"],
                          capture_output=True, text=True, timeout=60)


def brutdroid_vendor(dest: Path, repo: str = "https://github.com/Brut-Security/BrutDroid",
                     runner=None) -> Path:
    """Clone BrutDroid một lần, ghi SHA hiện tại vào BRUTDROID.sha."""
    dest = Path(dest)
    if (dest / "BrutDroid.py").exists() and (dest / "BRUTDROID.sha").exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = (runner or subprocess.run)(["git", "clone", "--quiet", repo, str(dest)],
                                   timeout=600)
    code = r.returncode if hasattr(r, "returncode") else (0 if r == 0 else 1)
    if code != 0:
        raise HarnessError("clone BrutDroid that bai", hint=str(repo))
    dest.mkdir(parents=True, exist_ok=True)
    sha = _rev_parse(dest).stdout.strip()
    (dest / "BRUTDROID.sha").write_text(sha, encoding="ascii")
    return dest
