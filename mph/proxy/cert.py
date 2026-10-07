"""Tải CA của Burp và cài vào system trust store của device.

Tên file theo chuẩn Android: <openssl subject_hash (MD5, 4 byte
little-endian)>.0 — apps API 24+ chỉ tin CA ở system store.
"""
import hashlib
import struct
import tempfile
import time
import urllib.request
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from ..errors import HarnessError

FETCH_ATTEMPTS = 6
FETCH_BACKOFF = 1.0


def fetch_der(port: int, opener=None) -> bytes:
    """Tải DER CA từ /cert của proxy listener; retry khi Burp còn warm-up."""
    if opener is None:
        opener = urllib.request.urlopen
    last_err: OSError | None = None
    for attempt in range(FETCH_ATTEMPTS):
        try:
            with opener(f"http://127.0.0.1:{port}/cert", timeout=10) as r:
                return r.read()
        except OSError as e:
            last_err = e
            if attempt < FETCH_ATTEMPTS - 1:
                time.sleep(FETCH_BACKOFF)
    raise HarnessError(
        f"khong tai duoc CA tu :{port}/cert sau {FETCH_ATTEMPTS} lan — Burp chay chua?",
        hint=str(last_err),
    ) from last_err


def pem_and_name(der: bytes) -> tuple[str, str]:
    """Trả (PEM, '<subject_hash>.0') cho cert DER."""
    cert = x509.load_der_x509_certificate(der)
    pem = cert.public_bytes(serialization.Encoding.PEM).decode("ascii")
    h = hashlib.md5(cert.subject.public_bytes()).digest()[:4]
    name = f"{struct.unpack('<I', h)[0]:08x}.0"
    return pem, name


def install_system_ca(der: bytes, adb) -> str:
    """Cài CA vào system trust store qua bind-mount (API 33/34).

    Từ API 34, CA thật nằm ở /apex/com.android.conscrypt/cacerts rồi bị
    bind sang /system/etc/security/cacerts lúc boot; /system bị verity khóa
    → copy apex sang /data/local/tmp, thêm CA Burp, bind đè CẢ HAI đường.
    Hiệu lực đến khi reboot (P2 thay bằng Magisk module bền vững).
    """
    pem, name = pem_and_name(der)
    r = adb.run("root", timeout=60)
    if not r.ok:
        raise HarnessError(
            "adb root that bai",
            hint=f"image google_apis moi cho phep adb root | {r.err}",
        )
    base = "/data/local/tmp/mph-cacerts"
    cmds = (
        f"rm -rf {base} && mkdir -p {base}",
        f"cp /apex/com.android.conscrypt/cacerts/* {base}/",
    )
    for c in cmds:
        r = adb.run("shell", c, timeout=60)
        if not r.ok:
            raise HarnessError(f"shell that bai: {c}", hint=r.err)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".0", delete=False, encoding="ascii"
    ) as f:
        f.write(pem)
        local = Path(f.name)
    remote = f"{base}/{name}"
    push = adb.run("push", str(local), remote, timeout=60)
    if not push.ok:
        raise HarnessError("push CA that bai", hint=push.err)
    fix = (
        f"chmod 644 {remote} && chown root:root {remote}",
        f"chcon u:object_r:system_security_cacerts_file:s0 {remote}",
        f"mount --bind {base} /apex/com.android.conscrypt/cacerts",
        f"mount --bind {base} /system/etc/security/cacerts",
    )
    for c in fix:
        r = adb.run("shell", c, timeout=60)
        if not r.ok and "mount" in c:
            raise HarnessError("bind-mount that bai", hint=r.err)
    return name
