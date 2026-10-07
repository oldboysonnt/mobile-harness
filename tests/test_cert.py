# tests/test_cert.py
import datetime
import hashlib
import struct

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from mph.proxy.cert import pem_and_name, fetch_der, install_system_ca

def _self_signed() -> bytes:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "portswigger-cnet")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256()))
    return cert.public_bytes(serialization.Encoding.DER)

def test_pem_and_name_format():
    der = _self_signed()
    pem, name = pem_and_name(der)
    assert pem.startswith("-----BEGIN CERTIFICATE-----")
    assert len(name) == 10 and name.endswith(".0") and name[:8].lower() == name[:8]
    cert = x509.load_der_x509_certificate(der)
    expect = struct.unpack("<I", hashlib.md5(
        cert.subject.public_bytes()).digest()[:4])[0]
    assert name == f"{expect:08x}.0"

def test_fetch_der(monkeypatch):
    der = _self_signed()

    class FakeResp:
        def read(self):
            return der

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("mph.proxy.cert.urllib.request.urlopen",
                        lambda url, timeout=None: FakeResp())
    assert fetch_der(8080) == der

class FakeAdb:
    def __init__(self):
        self.calls = []

    def run(self, *args, timeout=60, device=True):
        self.calls.append(args)
        return type("R", (), {"ok": True, "out": "", "err": "", "code": 0})()

def test_install_overwrites():
    der = _self_signed()
    a = FakeAdb()
    n1 = install_system_ca(der, a)
    n2 = install_system_ca(der, a)
    assert n1 == n2 and len(a.calls) >= 8  # 2 lần × (root+remount+push+chmod)
    pushed = [c for c in a.calls if c[0] == "push"]
    assert len(pushed) == 2
    assert all(c[2].endswith(n1) for c in pushed)
