"""Tải/pin artifact ngoài: magisk, shamiko, PIF, strongr, spic, rootAVD."""
import json
import os
import subprocess
import urllib.request
from pathlib import Path

from .errors import HarnessError


def download(url: str, dest: Path, fetch=None) -> Path:
    """Tải về dest; marker `.ok` xác nhận hoàn chỉnh (file nửa vời tự tải lại)."""
    dest = Path(dest)
    marker = dest.with_suffix(dest.suffix + ".ok")
    if dest.exists() and marker.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()  # thiếu marker → coi như hỏng
    (fetch or urllib.request.urlretrieve)(url, dest)
    marker.write_text("ok", encoding="ascii")
    return dest


def _api(slug: str) -> str:
    return f"https://api.github.com/repos/{slug}/releases/latest"


def _default_fj(url: str):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def resolve_latest(slugs, fetch_json=None, suffix: str = ".zip") -> tuple[str, str]:
    """Thử lần lượt các repo; trả (slug, asset_url) cái đầu có release khớp suffix."""
    fj = fetch_json or _default_fj
    tried = []
    for slug in slugs:
        tried.append(slug)
        try:
            assets = fj(_api(slug))
        except OSError:
            continue
        for a in assets if isinstance(assets, list) else []:
            if str(a.get("name", "")).endswith(suffix):
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


def vendor_all(cfg, fetch=None, fetch_json=None) -> dict:
    """Đảm bảo mọi artifact tồn tại trong tools/; trả map tên → đường dẫn."""
    tools = Path(cfg.tools_dir)
    got: dict[str, Path] = {}
    _s, a_magisk = resolve_latest([cfg.magisk_slug], fetch_json, ".apk")
    got["magisk"] = download(a_magisk, tools / "magisk.apk", fetch)
    _s, a_shamiko = resolve_latest([cfg.shamiko_slug], fetch_json, ".zip")
    got["shamiko"] = download(a_shamiko, tools / "shamiko.zip", fetch)
    _slug, a_pif = resolve_latest(cfg.pif_slugs, fetch_json, ".zip")
    got["pif"] = download(a_pif, tools / "pif.zip", fetch)
    furl = cfg.frida_server_url_tpl.format(ver=_frida_ver(cfg))
    got["frida-server"] = download(furl, tools / "frida-server.xz", fetch)
    _s, a_spic = resolve_latest([cfg.spic_slug], fetch_json, ".apk")
    got["spic"] = download(a_spic, tools / "spic.apk", fetch)
    ra_dir = tools / "rootavd"
    if not (ra_dir / "rootAVD.sh").exists():
        tgz = download(cfg.rootavd_url, tools / "rootavd.tar.gz", fetch)
        tools.mkdir(parents=True, exist_ok=True)
        untar(tgz, tools)
        inner = tools / "rootAVD-master"
        if ra_dir.exists():
            raise HarnessError("rootavd/ da ton tai",
                                hint="xoa tools/rootavd va chay lai")
        inner.rename(ra_dir)
    for sh in ra_dir.glob("*.sh"):
        os.chmod(sh, 0o755)
    got["rootavd"] = ra_dir
    return got
