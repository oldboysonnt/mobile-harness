"""Tải CA của Burp và cài vào system trust store của device.

Tên file theo chuẩn Android: <openssl subject_hash (MD5, 4 byte
little-endian)>.0 — apps API 24+ chỉ tin CA ở system store.
"""
import hashlib
import struct
import tempfile
import urllib.request
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from ..errors import HarnessError


def fetch_der(port: int, opener=None) -> bytes:
    """Tải DER CA từ endpoint /cert của proxy listener."""
    if opener is None:
        opener = urllib.request.urlopen
    try:
        with opener(f"http://127.0.0.1:{port}/cert", timeout=10) as r:
            return r.read()
    except OSError as e:
        raise HarnessError(
            f"khong tai duoc CA tu :{port}/cert — Burp chay chua?",
            hint=str(e),
        ) from e


def pem_and_name(der: bytes) -> tuple[str, str]:
    """Trả (PEM, '<subject_hash>.0') cho cert DER."""
    cert = x509.load_der_x509_certificate(der)
    pem = cert.public_bytes(serialization.Encoding.PEM).decode("ascii")
    h = hashlib.md5(cert.subject.public_bytes()).digest()[:4]
    name = f"{struct.unpack('<I', h)[0]:08x}.0"
    return pem, name


def install_system_ca(der: bytes, adb) -> str:
    """adb root + remount, đẩy CA vào /system/etc/security/cacerts; idempotent."""
    pem, name = pem_and_name(der)
    for args, hint in (
        (("root",), "image google_apis moi cho phep adb root"),
        (("remount",), "thu: adb disable-verity && adb reboot && remount"),
    ):
        r = adb.run(*args, timeout=60, device=False)
        if not r.ok:
            raise HarnessError(f"adb {args[0]} that bai", hint=hint)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".0", delete=False, encoding="ascii"
    ) as f:
        f.write(pem)
        local = Path(f.name)
    remote = f"/system/etc/security/cacerts/{name}"
    push = adb.run("push", str(local), remote, timeout=60, device=False)
    if not push.ok:
        raise HarnessError("push CA that bai", hint=push.err)
    adb.run("shell", "chmod", "644", remote)
    return name
