"""Tải/pin artifact ngoài: magisk, shamiko, PIF, strongr, spic, rootAVD."""
import json
import os
import subprocess
import urllib.request
from pathlib import Path

from .errors import HarnessError


def download(url: str, dest: Path, fetch=None) -> Path:
    """Tải về dest; marker `.ok` chứa URL — khác URL (đổi version) → tải lại."""
    dest = Path(dest)
    marker = dest.with_suffix(dest.suffix + ".ok")
    if dest.exists() and marker.exists() and marker.read_text(
            encoding="ascii", errors="replace").strip() == url:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()  # thiếu/hết hạn marker → coi như hỏng
    (fetch or urllib.request.urlretrieve)(url, dest)
    marker.write_text(url, encoding="ascii")
    return dest


def _api(slug: str) -> str:
    return f"https://api.github.com/repos/{slug}/releases/latest"


def _default_fj(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "mph-harness"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    return d.get("assets", []) if isinstance(d, dict) else d


def resolve_latest(slugs, fetch_json=None, suffix: str = ".zip",
                   contains: str | None = None) -> tuple[str, str]:
    """Thử lần lượt các repo; trả (slug, asset_url) khớp suffix (+contains)."""
    fj = fetch_json or _default_fj
    tried = []
    for slug in slugs:
        tried.append(slug)
        try:
            assets = fj(_api(slug))
        except OSError:
            continue
        for a in assets if isinstance(assets, list) else []:
            name = str(a.get("name", ""))
            if name.endswith(suffix) and (contains is None or contains in name):
                return slug, a["browser_download_url"]
    raise HarnessError("khong resolve duoc release",
                        hint=f"da thu: {', '.join(tried)} (suffix {suffix})")


def untar(src: Path, dest: Path) -> None:
    """bsdtar giải nén zip/xz/tar.* (có sẵn Windows 11)."""
    r = subprocess.run(["tar", "-xf", str(src), "-C", str(dest)],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise HarnessError(f"giai nen that bai: {Path(src).name}", hint=r.stderr)


def _frida_ver(cfg) -> str:
    if cfg.frida_client_ver != "auto":
        return cfg.frida_client_ver
    import frida  # pip frida đã cài — server phải khớp version client
    return frida.__version__


def _have(tools: Path, name: str, url: str = "") -> bool:
    """Artifact đã vendored (marker khớp URL; url rỗng = chỉ cần marker)."""
    dest = tools / name
    marker = dest.with_suffix(dest.suffix + ".ok")
    if not (dest.exists() and marker.exists()):
        return False
    if not url:
        return True
    return marker.read_text(encoding="ascii", errors="replace").strip() == url


def vendor_all(cfg, fetch=None, fetch_json=None) -> dict:
    """Đảm bảo mọi artifact tồn tại; KHÔNG gọi API khi đã vendored đủ."""
    tools = Path(cfg.tools_dir)
    got: dict[str, Path] = {}
    furl = cfg.frida_server_url_tpl.format(ver=_frida_ver(cfg))
    if not _have(tools, "magisk.apk"):
        _s, a = resolve_latest([cfg.magisk_slug], fetch_json, ".apk",
                               contains="Magisk-v")
        got["magisk"] = download(a, tools / "magisk.apk", fetch)
    else:
        got["magisk"] = tools / "magisk.apk"
    if not _have(tools, "shamiko.zip"):
        _s, a = resolve_latest([cfg.shamiko_slug], fetch_json, ".zip")
        got["shamiko"] = download(a, tools / "shamiko.zip", fetch)
    else:
        got["shamiko"] = tools / "shamiko.zip"
    if not _have(tools, "pif.zip"):
        _slug, a = resolve_latest(cfg.pif_slugs, fetch_json, ".zip")
        got["pif"] = download(a, tools / "pif.zip", fetch)
    else:
        got["pif"] = tools / "pif.zip"
    got["frida-server"] = (download(furl, tools / "frida-server.xz", fetch)
                           if not _have(tools, "frida-server.xz", furl)
                           else tools / "frida-server.xz")
    if not _have(tools, "spic.apk"):
        _s, a = resolve_latest([cfg.spic_slug], fetch_json, ".apk")
        got["spic"] = download(a, tools / "spic.apk", fetch)
    else:
        got["spic"] = tools / "spic.apk"
    ra_dir = tools / "rootavd"
    if not (ra_dir / "rootAVD.sh").exists():
        tgz = download(cfg.rootavd_url, tools / "rootavd.tar.gz", fetch)
        tools.mkdir(parents=True, exist_ok=True)
        untar(tgz, tools)
        inner = tools / "rootAVD-master"
        if ra_dir.exists():
            raise HarnessError("rootavd/ da ton tai (partial state)",
                                hint="xoa tools/rootavd va chay lai")
        inner.rename(ra_dir)
    for sh in ra_dir.glob("*.sh"):
        os.chmod(sh, 0o755)
    got["rootavd"] = ra_dir
    return got
