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


def resolve_latest(slugs, fetch_json=None) -> tuple[str, str]:
    """Thử lần lượt các repo; trả (slug, asset_zip_url) cái đầu có release."""
    fj = fetch_json or _default_fj
    tried = []
    for slug in slugs:
        tried.append(slug)
        try:
            assets = fj(_api(slug))
        except OSError:
            continue
        for a in assets if isinstance(assets, list) else []:
            if str(a.get("name", "")).endswith(".zip"):
                return slug, a["browser_download_url"]
    raise HarnessError("khong resolve duoc PIF release",
                        hint=f"da thu: {', '.join(tried)}")


def untar(src: Path, dest: Path) -> None:
    """bsdtar giải nén zip/xz/tar.* (có sẵn Windows 11)."""
    r = subprocess.run(["tar", "-xf", str(src), "-C", str(dest)],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise HarnessError(f"giai nen that bai: {Path(src).name}", hint=r.stderr)


def vendor_all(cfg, fetch=None, fetch_json=None) -> dict:
    """Đảm bảo mọi artifact tồn tại trong tools/; trả map tên → đường dẫn."""
    tools = Path(cfg.tools_dir)
    got: dict[str, Path] = {}
    got["magisk"] = download(cfg.magisk_url, tools / "magisk.apk", fetch)
    got["shamiko"] = download(cfg.shamiko_url, tools / "shamiko.zip", fetch)
    _slug, asset = resolve_latest(cfg.pif_slugs, fetch_json)
    got["pif"] = download(asset, tools / "pif.zip", fetch)
    surl = cfg.strongr_url_tpl.format(ver=cfg.frida_client_ver)
    got["strongr"] = download(surl, tools / "strongr.xz", fetch)
    got["spic"] = download(cfg.spic_url, tools / "spic.apk", fetch)
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
