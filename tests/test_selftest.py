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
    host_verify = staticmethod(lambda pem, port: ("200", ""))
    device_route_probe = staticmethod(lambda adb, port: True)

    @staticmethod
    def device_https_probe(adb, port):
        return "000", "connection refused"

class FakeCfg:
    def __init__(self, tmp_path):
        self.workspace = tmp_path
        self.proxy_port = 8082

def test_p1_fails_when_no_route(tmp_path):
    class DepsNoRoute(DepsFail):
        device_route_probe = staticmethod(lambda adb, port: False)
    ok, rows = run_p1(FakeCfg(tmp_path), deps=DepsNoRoute)
    assert ok is False
    last = rows[-1]
    assert last[0] == "device-route" and last[1] is False

def test_p1_fails_when_host_ca_verify_fails(tmp_path):
    class DepsBadCA(DepsFail):
        host_verify = staticmethod(lambda pem, port: ("000", "ssl cert problem"))
    ok, rows = run_p1(FakeCfg(tmp_path), deps=DepsBadCA)
    assert ok is False
    row = next(r for r in rows if r[0] == "ca-host")
    assert row[1] is False and "ssl" in row[2]

def test_p1_green_with_nocurl_device(tmp_path):
    class DepsOK(DepsFail):
        @staticmethod
        def device_https_probe(adb, port):
            return "nocurl", "image khong co curl — da chung minh bang nc + host"
    ok, rows = run_p1(FakeCfg(tmp_path), deps=DepsOK)
    assert ok is True
    assert [r[0] for r in rows] == [
        "boot", "burp", "ca", "ca-host", "proxy-on", "device-route", "https-probe",
    ]

def test_p1_green_with_device_curl(tmp_path):
    class DepsCurl(DepsFail):
        @staticmethod
        def device_https_probe(adb, port):
            return "200", ""
    ok, rows = run_p1(FakeCfg(tmp_path), deps=DepsCurl)
    assert ok is True
