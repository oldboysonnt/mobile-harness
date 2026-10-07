"""Load cấu hình pin-version từ mph.toml + env override.

Ruling (2026-10-07, executing-plans): máy này không có BurpSuitePro.exe —
Burp chạy qua java + burpsuite_pro.jar trong <burp_bin>/BurpSuitePro/.
Resolver: BURP_PATH env -> exe -> bat -> <dir>/BurpSuitePro.exe -> jar.
Task 5 dùng burp_exe (jar) để dựng lệnh java với -javaagent như burp.vbs.
"""
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .errors import HarnessError

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_TOML = _REPO_ROOT / "mph.toml"

_BURP_CANDIDATES = (
    r"C:\Program Files\Burp\bin\BurpSuitePro.exe",
    r"C:\Program Files\Burp\bin\BurpSuitePro.bat",
    r"C:\Program Files\Burp\bin\BurpSuitePro\BurpSuitePro.exe",
    r"C:\Program Files\Burp\bin\BurpSuitePro\burpsuite_pro.jar",
)


@dataclass(frozen=True)
class Config:
    """Snapshot cấu hình bất biến của một lần chạy."""

    sdk: Path
    burp_exe: Path | None
    burp_bin: Path
    git_bash: Path
    avd_name: str
    image: str
    proxy_port: int
    burp_mcp_port: int
    workspace: Path
    magisk_slug: str = "topjohnwu/Magisk"
    shamiko_slug: str = "LSPosed/LSPosed.github.io"
    pif_slugs: tuple = (
        "osm0sis/PlayIntegrityFork",
        "chiteroman/PlayIntegrityFork",
        "jyotidwi/PlayIntegrityFix",
    )
    frida_server_url_tpl: str = (
        "https://github.com/frida/frida/releases/download/{ver}/"
        "frida-server-{ver}-android-x86_64.xz"
    )
    frida_engine: str = "stock"
    frida_client_ver: str = "auto"
    frida_alias: str = "sysmondd"
    frida_port: int = 27042
    spic_slug: str = "herzhenr/spic-android"
    rootavd_url: str = (
        "https://gitlab.com/newbit/rootAVD/-/archive/master/rootAVD-master.tar.gz"
    )
    tools_dir: Path = _REPO_ROOT / "tools"
    fingerprints_dir: Path = _REPO_ROOT / "fingerprints"


def _resolve_burp() -> Path | None:
    """Trả đường dẫn Burp hoặc None (doctor báo, lệnh cần Burp mới raise)."""
    if os.environ.get("BURP_PATH"):
        return Path(os.environ["BURP_PATH"])
    for c in _BURP_CANDIDATES:
        if Path(c).exists():
            return Path(c)
    return None


def load_config(path: Path | None = None) -> Config:
    """Đọc mph.toml (mặc định repo root), env override ANDROID_HOME/BURP_PATH."""
    data: dict = {}
    f = path or _DEFAULT_TOML
    if f.exists():
        data = tomllib.loads(f.read_text(encoding="utf-8"))
    p = data.get("paths", {})
    avd = data.get("avd", {})
    px = data.get("proxy", {})
    root = data.get("root", {})
    frida = data.get("frida", {})
    vendor = data.get("vendor", {})
    sdk = Path(
        os.environ.get("ANDROID_HOME")
        or p.get("sdk", r"C:\Users\sonnt\AppData\Local\Android\Sdk")
    )
    return Config(
        sdk=sdk,
        burp_exe=_resolve_burp(),
        burp_bin=Path(p.get("burp_bin", r"C:\Program Files\Burp\bin")),
        git_bash=Path(p.get("git_bash", r"C:\Program Files\Git\bin\bash.exe")),
        avd_name=str(avd.get("name", "mph_avd")),
        image=str(avd.get("image", "system-images;android-34;google_apis;x86_64")),
        proxy_port=int(px.get("port", 8080)),
        burp_mcp_port=int(px.get("burp_mcp_port", 9876)),
        workspace=_REPO_ROOT / data.get("workspace", {}).get("root", "workspace"),
        magisk_slug=str(root.get("magisk_slug", "topjohnwu/Magisk")),
        shamiko_slug=str(root.get("shamiko_slug", "LSPosed/LSPosed.github.io")),
        pif_slugs=tuple(root.get("pif_slugs", [
            "osm0sis/PlayIntegrityFork",
            "chiteroman/PlayIntegrityFork",
            "jyotidwi/PlayIntegrityFix",
        ])),
        frida_server_url_tpl=str(frida.get(
            "server_url_tpl",
            "https://github.com/frida/frida/releases/download/{ver}/"
            "frida-server-{ver}-android-x86_64.xz",
        )),
        frida_engine=str(frida.get("engine", "stock")),
        frida_client_ver=str(frida.get("client_ver", "auto")),
        frida_alias=str(frida.get("alias", "sysmondd")),
        frida_port=int(frida.get("port", 27042)),
        spic_slug=str(vendor.get("spic_slug", "herzhenr/spic-android")),
        rootavd_url=str(vendor.get(
            "rootavd_url",
            "https://gitlab.com/newbit/rootAVD/-/archive/master/rootAVD-master.tar.gz",
        )),
        tools_dir=_REPO_ROOT / "tools",
        fingerprints_dir=_REPO_ROOT / "fingerprints",
    )
