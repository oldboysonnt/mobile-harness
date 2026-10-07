# tests/test_selftest.py
from mph.selftest import run_p1

class DepsFail:
    avd_serial = staticmethod(lambda: "emulator-5554")
    wait_booted = staticmethod(lambda *a, **k: True)
    adb_root = staticmethod(lambda adb: adb)
    adb_factory = staticmethod(lambda serial: object())
    burp_start = staticmethod(lambda *a, **k: 123)
    fetch_der = staticmethod(lambda port: b"\x30\x03\x02\x01\x01")
    install_system_ca = staticmethod(lambda der, adb: "a1b2c3d4.0")
    proxy_on = staticmethod(lambda adb, port: None)

    @staticmethod
    def device_https_probe(adb, port):
        return "000", "connection refused"

class FakeCfg:
    def __init__(self, tmp_path):
        self.workspace = tmp_path
        self.proxy_port = 8082

def test_p1_fails_at_https_with_diagnosis(tmp_path):
    ok, rows = run_p1(FakeCfg(tmp_path), deps=DepsFail)
    assert ok is False
    last = rows[-1]
    assert last[0] == "https-probe" and last[1] is False
    assert "000" in last[2] or "refused" in last[2]

def test_p1_all_green(tmp_path):
    class DepsOK(DepsFail):
        @staticmethod
        def device_https_probe(adb, port):
            return "200", ""
    ok, rows = run_p1(FakeCfg(tmp_path), deps=DepsOK)
    assert ok is True
    assert [r[0] for r in rows] == ["boot", "burp", "ca", "proxy-on", "https-probe"]
