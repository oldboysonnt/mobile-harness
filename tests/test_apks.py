# tests/test_apks.py
from pathlib import Path

import pytest

from mph.errors import HarnessError
from mph.re.apks import app_workspace, install_apk, list_packages, pull_apk

class FakeAdb:
    def __init__(self, pm_path_out="package:/data/app/x/base.apk"):
        self.pm_path_out = pm_path_out
        self.calls = []

    def run(self, *args, timeout=60, device=True):
        self.calls.append(" ".join(args))
        out = ""
        if args[:2] == ("shell", "pm") and "path" in args:
            out = self.pm_path_out
        return type("R", (), {"ok": True, "out": out, "err": "", "code": 0})()

def test_app_workspace_layout(tmp_path):
    class C:
        workspace = tmp_path
    p = app_workspace(C(), "myapp")
    assert p == tmp_path / "myapp" and p.name == "myapp"

def test_list_packages_parses():
    a = FakeAdb()
    a.run = lambda *args, timeout=60, device=True: type(
        "R", (), {"ok": True, "out": "package:com.a\npackage:com.b\n",
                  "err": "", "code": 0})()
    assert list_packages(a) == ["com.a", "com.b"]

def test_pull_picks_base_apk(tmp_path):
    a = FakeAdb("package:/data/app/x/split_config.apk\npackage:/data/app/x/base.apk\n")
    out = pull_apk(a, "com.x", tmp_path)
    assert out == tmp_path / "com.x.apk"
    pulled = [c for c in a.calls if c.startswith("pull")]
    assert any("base.apk" in c for c in pulled)

def test_pull_missing_package_raises(tmp_path):
    a = FakeAdb("")
    with pytest.raises(HarnessError):
        pull_apk(a, "com.none", tmp_path)

def test_install_uses_r_flag():
    a = FakeAdb()
    assert install_apk(a, Path("x.apk")) is True
    assert any("install -r" in c for c in a.calls)

def test_app_workspace_rejects_escape():
    class C:
        workspace = Path("C:/ws")
    import pytest as _p
    from mph.errors import HarnessError as HE
    for bad in ("..", "../x", "a/b", "C:/evil", "a\b", ""):
        with _p.raises(HE):
            app_workspace(C(), bad)
