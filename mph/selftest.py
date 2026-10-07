"""Selftest P1: boot → burp → CA → proxy → HTTPS qua Burp.

Ruling (2026-10-07): image API 34 không có curl/wget (toybox chỉ có nc) —
oracle tách 3 mảnh: (a) nc CONNECT từ device chứng minh routing,
(b) host curl --cacert chứng minh CA + intercept TLS, (c) curl device nếu có.
"""
from dataclasses import dataclass
from pathlib import Path

from .device import avd as avd_mod
from .device.adb import Adb
from .proxy import burp as burp_mod
from .proxy import cert as cert_mod
from .proxy import route as route_mod


def _device_https_probe(adb: Adb, port: int) -> tuple[str, str]:
    have = adb.run("shell", "command -v curl")
    if not have.ok or "curl" not in have.out:
        return "nocurl", "image khong co curl — da chung minh bang nc + host"
    r = adb.run(
        "shell",
        f"curl -sx http://127.0.0.1:{port} -o /dev/null -w %{{http_code}} https://example.com",
        timeout=60,
    )
    return r.out.strip() or "000", r.err.strip()


def _device_route_probe(adb: Adb, port: int) -> bool:
    """CONNECT handshake qua proxy từ trong device — toybox nc cần giữ stdin mở."""
    r = adb.run(
        "shell",
        f'(printf "CONNECT example.com:443 HTTP/1.1\\r\\nHost: example.com:443\\r\\n\\r\\n"; sleep 2) | nc 127.0.0.1 {port}',
        timeout=30,
    )
    return r.ok and "200" in r.out


def _host_verify(pem_path: Path, port: int) -> tuple[str, str]:
    """Host-side: HTTPS qua Burp với CA vừa cài (stdlib, không lệch curl build)."""
    import http.client
    import ssl

    ctx = ssl.create_default_context(cafile=str(pem_path))
    conn = http.client.HTTPSConnection("127.0.0.1", port, context=ctx, timeout=30)
    try:
        conn.set_tunnel("example.com", 443)
        conn.request("GET", "/", headers={"Host": "example.com"})
        resp = conn.getresponse()
        resp.read()
        return str(resp.status), ""
    except (OSError, ssl.SSLError) as e:
        return "000", str(e)
    finally:
        conn.close()


def _adb_root(adb: Adb) -> Adb:
    adb.run("root")
    return adb


@dataclass(frozen=True)
class Deps:
    avd_serial = staticmethod(avd_mod.avd_serial)
    wait_booted = staticmethod(avd_mod.wait_booted)
    adb_root = staticmethod(_adb_root)
    adb_factory = staticmethod(lambda serial: Adb(serial=serial))
    burp_start = staticmethod(burp_mod.burp_start)
    fetch_der = staticmethod(cert_mod.fetch_der)
    install_system_ca = staticmethod(cert_mod.install_system_ca)
    proxy_on = staticmethod(route_mod.proxy_on)
    host_verify = staticmethod(_host_verify)
    device_route_probe = staticmethod(_device_route_probe)
    device_https_probe = staticmethod(_device_https_probe)


def run_p1(cfg, deps: Deps | None = None) -> tuple[bool, list[tuple[str, bool, str]]]:
    """Chạy chuỗi bước P1; trả (ok, [(tên, ok, chi tiết)])."""
    d = deps or Deps()
    rows: list[tuple[str, bool, str]] = []

    def step(name, fn, *a):
        try:
            detail = fn(*a) or "ok"
            rows.append((name, True, str(detail)))
            return True
        except Exception as e:  # noqa: BLE001 — selftest tổng hợp mọi lỗi
            rows.append((name, False, str(e)))
            return False

    serial = d.avd_serial()
    if not serial or not step("boot", d.wait_booted, serial, d.adb_factory(serial)):
        if not serial:
            rows.append(("boot", False, "khong thay emulator serial — chay: mph setup run"))
        return False, rows
    adb = d.adb_root(d.adb_factory(serial))
    ws = Path(cfg.workspace)
    if not step(
        "burp",
        d.burp_start,
        cfg,
        ws / "_shared" / "burp" / "main.burp",
        ws / "_shared" / "burp" / "main.json",
    ):
        return False, rows
    der = d.fetch_der(cfg.proxy_port)
    step("ca", d.install_system_ca, der, adb)

    pem, name = cert_mod.pem_and_name(der)
    pem_path = ws / "_shared" / "burp-ca" / name
    pem_path.parent.mkdir(parents=True, exist_ok=True)
    pem_path.write_text(pem, encoding="ascii")
    code, err = d.host_verify(pem_path, cfg.proxy_port)
    ca_ok = code == "200"
    rows.append(("ca-host", ca_ok, f"code={code} {err}".strip()))

    step("proxy-on", d.proxy_on, adb, cfg.proxy_port)
    route_ok = d.device_route_probe(adb, cfg.proxy_port)
    rows.append(("device-route", route_ok, "CONNECT qua proxy" if route_ok else "nc CONNECT khong thay 200"))

    dcode, derr = d.device_https_probe(adb, cfg.proxy_port)
    rows.append(("https-probe", dcode == "200", f"code={dcode} {derr}".strip()))

    ok = ca_ok and route_ok and (dcode == "200" or dcode == "nocurl")
    return ok, rows
