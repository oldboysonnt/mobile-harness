# tests/test_selftest.py
from pathlib import Path
import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from mph.selftest import run_p1

def _self_signed() -> bytes:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "selftest-ca")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256()))
    return cert.public_bytes(serialization.Encoding.DER)

class DepsFail:
    avd_serial = staticmethod(lambda: "emulator-5554")
    wait_booted = staticmethod(lambda *a, **k: True)
    adb_root = staticmethod(lambda adb: adb)
    adb_factory = staticmethod(lambda serial: object())
    burp_start = staticmethod(lambda *a, **k: 123)
    fetch_der = staticmethod(lambda port: _self_signed())
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
    row = next(r for r in rows if r[0] == "device-route")
    assert row[1] is False

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

def test_p1_boot_false_fails(tmp_path):
    class DepsBootTimeout(DepsFail):
        wait_booted = staticmethod(lambda *a, **k: False)
    ok, rows = run_p1(FakeCfg(tmp_path), deps=DepsBootTimeout)
    assert ok is False
    row = next(r for r in rows if r[0] == "boot")
    assert row[1] is False  # không được coerce False thành "ok"

def test_p1_ca_failure_stays_red(tmp_path):
    class DepsBadCA(DepsFail):
        @staticmethod
        def install_system_ca(der, adb):
            raise RuntimeError("bind-mount that bai")
    ok, rows = run_p1(FakeCfg(tmp_path), deps=DepsBadCA)
    assert ok is False  # dù host-verify 200 + nocurl

def test_p1_fetch_der_failure_structured(tmp_path):
    from mph.errors import HarnessError
    class DepsNoFetch(DepsFail):
        @staticmethod
        def fetch_der(port):
            raise HarnessError("khong tai duoc CA")
    ok, rows = run_p1(FakeCfg(tmp_path), deps=DepsNoFetch)  # không raise ra ngoài
    assert ok is False
    assert any(r[0] == "ca" and r[1] is False for r in rows)

def test_p1_corrupt_der_structured(tmp_path):
    class DepsJunk(DepsFail):
        @staticmethod
        def fetch_der(port):
            return b"khong phai cert"
    ok, rows = run_p1(FakeCfg(tmp_path), deps=DepsJunk)  # ValueError bị bắt
    assert ok is False
    assert any(r[0] == "ca" and r[1] is False for r in rows)

def test_p2_extends_p1(tmp_path):
    from mph.selftest import run_p2
    class DepsP2(DepsFail):
        device_route_probe = staticmethod(lambda adb, port: True)  # P1 xanh
        @staticmethod
        def device_https_probe(adb, port):
            return "nocurl", "skipped by ruling"
        magisk_present = staticmethod(lambda adb: True)
        integrity_status = staticmethod(lambda adb, cfg: {
            "shamiko": True, "pif": True, "zygisk": True,
            "denylist": 2, "fingerprints": ["pixel8"]})
        frida_start = staticmethod(lambda adb, cfg: "/data/local/tmp/sysmondd")
        frida_health = staticmethod(lambda adb: True)
        unpin_smoke = staticmethod(lambda adb, cfg: (0, "smoke"))
    ok, rows = run_p2(FakeCfg(tmp_path), deps=DepsP2)
    names = [r[0] for r in rows]
    assert ok is True
    assert {"magisk", "integrity", "frida", "unpin-smoke"} <= set(names)

def test_p3_green(tmp_path):
    from mph.selftest import run_p3
    class DepsP3(DepsFail):
        device_route_probe = staticmethod(lambda adb, port: True)
        @staticmethod
        def device_https_probe(adb, port):
            return "nocurl", "skipped"
        magisk_present = staticmethod(lambda adb: True)
        integrity_status = staticmethod(lambda adb, cfg: {"shamiko": True,
            "pif": True, "zygisk": True, "denylist": 1, "fingerprints": []})
        frida_start = staticmethod(lambda adb, cfg: "/data/local/tmp/sysmondd")
        frida_health = staticmethod(lambda adb: True)
        unpin_smoke = staticmethod(lambda adb, cfg: (0, ""))
        pull_apk = staticmethod(lambda adb, pkg, dest: dest / f"{pkg}.apk")
        decompile = staticmethod(lambda apk, out: out)
        @staticmethod
        def parse_manifest(jadx_out):
            return {"package": "x", "exported": {"activities": [".Main"]},
                    "deeplinks": [], "permissions": []}
        ensure_indexed = staticmethod(lambda cfg, out: {"status": "ok"})
    ok, rows = run_p3(FakeCfg(tmp_path), deps=DepsP3)
    names = [r[0] for r in rows]
    assert ok is True
    assert {"pull", "jadx", "manifest", "index"} <= set(names)

def test_p4_green(tmp_path):
    from mph.selftest import run_p4
    class DepsP4(DepsFail):
        device_route_probe = staticmethod(lambda adb, port: True)
        @staticmethod
        def device_https_probe(adb, port):
            return "nocurl", "skipped"
        magisk_present = staticmethod(lambda adb: True)
        integrity_status = staticmethod(lambda adb, cfg: {"shamiko": True,
            "pif": True, "zygisk": True, "denylist": 1, "fingerprints": []})
        frida_start = staticmethod(lambda adb, cfg: "/x")
        frida_health = staticmethod(lambda adb: True)
        unpin_smoke = staticmethod(lambda adb, cfg: (0, ""))
        pull_apk = staticmethod(lambda adb, pkg, dest: dest / f"{pkg}.apk")
        @staticmethod
        def decompile(apk, out):
            return out
        @staticmethod
        def parse_manifest(jadx_out):
            return {"package": "x", "exported": {}, "deeplinks": [],
                    "permissions": []}
        ensure_indexed = staticmethod(lambda cfg, out: {"status": "ok"})
        wm_size = staticmethod(lambda adb: (1080, 2400))
        @staticmethod
        def screenshot(adb, dest):
            Path(str(dest)).parent.mkdir(parents=True, exist_ok=True)
            Path(str(dest)).write_bytes(b"\x89PNG fake")
            return {"path": str(dest), "screen": [1080, 2400], "png_bytes": 9}
        ui_dump = staticmethod(lambda adb, dest: Path(str(dest)))
        tap_smoke = staticmethod(lambda adb: "HOME+tap ok")
        spic_check = staticmethod(lambda adb, cfg:
                                  {"verdict": "MEETS_BASIC", "evidence": "x.png"})
    ok, rows = run_p4(FakeCfg(tmp_path), deps=DepsP4)
    names = [r[0] for r in rows]
    assert ok is True
    assert {"wm-size", "screenshot", "ui-dump", "tap-smoke",
            "spic-verdict"} <= set(names)
