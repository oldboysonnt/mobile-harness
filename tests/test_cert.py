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

def test_fetch_der_retries_transient_reset(monkeypatch):
    der = _self_signed()
    attempts = []

    class FakeResp:
        def read(self):
            return der

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def flaky(url, timeout=None):
        attempts.append(url)
        if len(attempts) < 3:  # Burp warm-up: port mở nhưng reset vài request đầu
            raise ConnectionResetError(10054, "reset")
        return FakeResp()

    monkeypatch.setattr("mph.proxy.cert.urllib.request.urlopen", flaky)
    monkeypatch.setattr("mph.proxy.cert.time.sleep", lambda s: None)
    assert fetch_der(8080) == der and len(attempts) == 3

class FakeAdb:
    def __init__(self):
        self.calls = []

    def su(self, cmd, timeout=60):
        return self.run("shell", f"su -c {cmd}", timeout=timeout)

    def run(self, *args, timeout=60, device=True):
        self.calls.append(args)
        return type("R", (), {"ok": True, "out": "", "err": "", "code": 0})()

def test_install_overwrites():
    der = _self_signed()
    a = FakeAdb()
    n1 = install_system_ca(der, a)
    n2 = install_system_ca(der, a)
    assert n1 == n2
    pushed = [c for c in a.calls if c[0] == "push"]
    assert len(pushed) == 2  # idempotent: chạy 2 lần, push 2 lần, cùng tên
    assert all(c[2].endswith(n1) for c in pushed)
    shell_cmds = [" ".join(c[1:]) for c in a.calls if c[0] == "shell"]
    assert any(j.startswith("umount /system/etc/security/cacerts") for j in shell_cmds)
    assert any("mount --bind" in j and "/apex/com.android.conscrypt/cacerts" in j
               for j in shell_cmds)
    assert any("mount --bind" in j and "/system/etc/security/cacerts" in j
               for j in shell_cmds)
    assert any(j.startswith("cp /apex/com.android.conscrypt/cacerts") for j in shell_cmds)
