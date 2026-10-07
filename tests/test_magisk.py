# tests/test_magisk.py
from pathlib import Path

import pytest

from mph.errors import HarnessError
from mph.root.magisk import (denylist_add, hide_emu_props, install_module,
                             require_magisk, zygisk_enable)

class FakeAdb:
    def __init__(self, su_ok=True):
        self.su_ok = su_ok
        self.calls = []

    def run(self, *args, timeout=60, device=True):
        self.calls.append(" ".join(args))
        ok = self.su_ok or not (args[0] == "shell" and "su" in args[:2])
        out = "29.4:M" if ("-v" in args and self.su_ok) else ""
        return type("R", (), {"ok": ok, "out": out, "err": "",
                              "code": 0 if ok else 1})()

def test_magisk_missing_fails_with_hint():
    with pytest.raises(HarnessError) as e:
        require_magisk(FakeAdb(su_ok=False))
    assert "mph root install" in str(e.value)

def test_zygisk_enables_and_restarts():
    a = FakeAdb()
    assert zygisk_enable(a) is True
    assert any("sqlite" in c and "zygisk" in c for c in a.calls)
    assert any("resetprop" in c or "setprop" in c for c in a.calls)

def test_denylist_add_includes_gms_and_target():
    a = FakeAdb()
    denylist_add(a, "com.victim.app")
    joined = " ; ".join(a.calls)
    assert "com.google.android.gms" in joined and "com.victim.app" in joined

def test_install_module_pushes_and_runs():
    a = FakeAdb()
    install_module(a, Path("tools/shamiko.zip"))
    assert any(c.startswith("push") and c.endswith(".zip") for c in a.calls)
    assert any("install-module" in c for c in a.calls)

def test_hide_emu_props_resets_qemu_markers():
    a = FakeAdb()
    hide_emu_props(a)
    joined = " ; ".join(a.calls)
    assert "ro.kernel.qemu" in joined and "ro.boot.qemu" in joined
    assert any("ro.product.device" in c for c in a.calls)
