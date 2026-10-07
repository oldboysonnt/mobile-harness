# tests/test_frida_server.py
from pathlib import Path

from mph.frida.server import frida_start, frida_stop, sanitize_alias

BANNED = {"frida", "hluda", "gum", "gadget"}

def test_alias_sanitized_charset():
    assert sanitize_alias("Sys-Mon!@#dd") == "sysmondd"

def test_alias_banned_gets_suffix():
    a = sanitize_alias("frida")
    assert a not in BANNED and a.startswith("frida")

def test_alias_ok_passthrough():
    assert sanitize_alias("sysmondd") == "sysmondd"

class FakeAdb:
    def __init__(self):
        self.calls = []

    def su(self, cmd, timeout=60):
        return self.run("shell", f"su -c {cmd}", timeout=timeout)

    def run(self, *args, timeout=60, device=True):
        self.calls.append(" ".join(args))
        return type("R", (), {"ok": True, "out": "", "err": "", "code": 0})()

def test_frida_start_pushes_alias_and_runs(tmp_path, monkeypatch):
    monkeypatch.setattr("mph.frida.server.unpack_strongr",
                        lambda xz, out: tmp_path / "bin")
    monkeypatch.setattr("mph.frida.server._wait_frida_ps", lambda adb: True)
    a = FakeAdb()
    remote = frida_start(a, tmp_path / "strongr.xz", alias="sysmondd", port=27047)
    joined = " ; ".join(a.calls)
    assert "/data/local/tmp/sysmondd" in joined and "27047" in joined
    assert remote == "/data/local/tmp/sysmondd"

def test_unpack_xz_creates_bin(tmp_path):
    import lzma
    payload = b"ELF_FAKE_BINARY" * 100
    xz = tmp_path / "server.xz"
    xz.write_bytes(lzma.compress(payload))
    from mph.frida.server import unpack_strongr
    out = unpack_strongr(xz, tmp_path)
    assert out.name == "frida-server-bin"
    assert out.read_bytes() == payload
    assert unpack_strongr(xz, tmp_path) == out  # idempotent

def test_frida_stop_kills_alias():
    a = FakeAdb()
    assert frida_stop(a, "sysmondd") is True
    assert any("pkill" in c and "sysmondd" in c for c in a.calls)
