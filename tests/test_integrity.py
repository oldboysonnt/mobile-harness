# tests/test_integrity.py
import json
from pathlib import Path

from mph.root.integrity import (PIF_MODULE_DIR, fingerprint_list,
                                fingerprint_use, integrity_install,
                                integrity_status)

class FakeAdb:
    def __init__(self):
        self.calls = []

    def su(self, cmd, timeout=60):
        return self.run("shell", f"su -c {cmd}", timeout=timeout)

    def run(self, *args, timeout=60, device=True):
        self.calls.append(" ".join(args))
        return type("R", (), {"ok": True, "out": "", "err": "", "code": 0})()

class FakeMagisk:
    def zygisk_enable(self, adb):
        return True

    def denylist_add(self, adb, pkg):
        return True

    def install_module(self, adb, z):
        adb.run("push", str(z), f"/data/local/tmp/{Path(z).name}")
        adb.run("shell", "su", "-c", f"magisk --install-module /data/local/tmp/{Path(z).name}")
        return True

def test_integrity_install_orchestrates(tmp_path, monkeypatch):
    import mph.root.integrity as I
    fake = FakeMagisk()
    monkeypatch.setattr(I, "zygisk_enable", fake.zygisk_enable)
    monkeypatch.setattr(I, "denylist_add", fake.denylist_add)
    monkeypatch.setattr(I, "install_module", fake.install_module)
    monkeypatch.setattr(I, "hide_emu_props", lambda adb: True)
    a = FakeAdb()

    class C:
        fingerprints_dir = tmp_path / "fp"
    got = integrity_install(a, C(), {"shamiko": tmp_path / "s.zip",
                                     "pif": tmp_path / "p.zip"})
    assert got["zygisk"] and got["shamiko"] and got["pif"]
    pushed = " ; ".join(a.calls)
    assert "s.zip" in pushed and "p.zip" in pushed

def test_fingerprint_use_pushes_json(tmp_path):
    fp = tmp_path / "fp"
    fp.mkdir()
    (fp / "pixel8.json").write_text(json.dumps({"MODEL": "Pixel 8"}),
                                    encoding="utf-8")
    a = FakeAdb()

    class C:
        fingerprints_dir = fp
    assert fingerprint_use(a, C(), "pixel8") is True
    assert any(PIF_MODULE_DIR in c and "pif.json" in c for c in a.calls)

def test_fingerprint_missing_name(tmp_path):
    a = FakeAdb()

    class C:
        fingerprints_dir = tmp_path / "fp"
    assert fingerprint_use(a, C(), "nope") is False

def test_status_shape(tmp_path):
    a = FakeAdb()

    class C:
        fingerprints_dir = tmp_path / "fp"
    st = integrity_status(a, C())
    assert set(st) == {"shamiko", "pif", "zygisk", "denylist", "fingerprints"}
