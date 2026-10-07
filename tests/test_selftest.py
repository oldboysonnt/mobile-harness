# tests/test_selftest.py
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
