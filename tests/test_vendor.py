# tests/test_vendor.py
import tarfile
from pathlib import Path

import pytest

from mph.errors import HarnessError
from mph.vendor import download, resolve_latest, untar, vendor_all

def _write_bytes(d, b: bytes) -> None:
    Path(d).write_bytes(b)

def _make_rootavd_tar(dest: Path) -> None:
    with tarfile.open(dest, "w:gz") as tf:
        f = dest.parent / "rootAVD.sh"
        f.write_text("#!/usr/bin/env bash\n")
        tf.add(f, arcname="rootAVD-master/rootAVD.sh")
        f.unlink()

def test_partial_download_refetched(tmp_path):
    dest = tmp_path / "x.zip"
    dest.write_bytes(b"half")            # file đỏng đảnh, không marker
    fetched = []
    def fetch(url, d):
        fetched.append(url)
        _write_bytes(d, b"full")
    download("https://x/y.zip", dest, fetch=fetch)
    assert dest.read_bytes() == b"full" and len(fetched) == 1
    download("https://x/y.zip", dest, fetch=fetch)   # lần 2: có marker → skip
    assert len(fetched) == 1 and (tmp_path / "x.zip.ok").exists()

def test_pif_resolver_fallback():
    def fj(url):
        if "first" in url:
            raise OSError("404")
        return [{"browser_download_url": "https://x/pif.zip",
                 "name": "pif.zip"}]
    repo, asset = resolve_latest(["first/repo", "second/repo"], fetch_json=fj)
    assert repo == "second/repo" and asset.endswith("pif.zip")

def test_pif_resolver_all_fail():
    with pytest.raises(HarnessError) as e:
        resolve_latest(["a/r1", "a/r2"],
                       fetch_json=lambda u: (_ for _ in ()).throw(OSError("404")))
    assert "a/r1" in str(e.value) and "a/r2" in str(e.value)

def test_untar_creates_nested(tmp_path):
    src = tmp_path / "t.tar.gz"
    with tarfile.open(src, "w:gz") as tf:
        f = tmp_path / "inner.txt"; f.write_text("hi")
        tf.add(f, arcname="rootAVD/inner.txt")
    out = tmp_path / "out"; out.mkdir()
    untar(src, out)
    assert (out / "rootAVD" / "inner.txt").read_text() == "hi"

def test_vendor_all_returns_expected_keys(tmp_path):
    class FakeCfg:
        magisk_slug = "topjohnwu/Magisk"
        shamiko_slug = "LSPosed/LSPosed.github.io"
        pif_slugs = ("osm0sis/PlayIntegrityFork",)
        spic_slug = "herzhenr/spic-android"
        rootavd_url = "u5"
        frida_server_url_tpl = "https://g/{ver}/frida-server.xz"
        frida_client_ver = "1.2.3"
        tools_dir = tmp_path / "tools"; fingerprints_dir = tmp_path / "fp"
    def fetch(url, d):
        if url == "u5":
            _make_rootavd_tar(Path(d))
        else:
            _write_bytes(d, b"data")
    def fj(url):
        out = []
        if "Magisk" in url:
            out = [{"browser_download_url": "u1", "name": "Magisk-v9.apk"}]
        elif "LSPosed" in url:
            out = [{"browser_download_url": "u2", "name": "Shamiko.zip"}]
        elif "spic" in url:
            out = [{"browser_download_url": "u4", "name": "spic.apk"}]
        else:
            out = [{"browser_download_url": "u3", "name": "pif.zip"}]
        return out
    got = vendor_all(FakeCfg(), fetch=fetch, fetch_json=fj)
    assert set(got) == {"magisk", "shamiko", "pif", "frida-server", "spic", "rootavd"}
    assert (tmp_path / "tools" / "frida-server.xz").exists()
    assert (tmp_path / "tools" / "rootavd" / "rootAVD.sh").exists()
