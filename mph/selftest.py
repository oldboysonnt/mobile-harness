"""Selftest P1/P2: boot → burp → CA → proxy → HTTPS → magisk → integrity → frida.

Ruling (2026-10-07): image API 34 không có curl/wget (toybox chỉ có nc) —
oracle tách 3 mảnh: (a) nc CONNECT từ device chứng minh routing,
(b) host curl --cacert chứng minh CA + intercept TLS, (c) curl device nếu có.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from .device import avd as avd_mod
from .device.adb import Adb
from .frida import server as frida_server
from .frida import scripts as frida_scripts
from .proxy import burp as burp_mod
from .proxy import cert as cert_mod
from .proxy import route as route_mod
from .root.integrity import integrity_status
from .root.rootavd import magisk_present


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


def _host_verify(pem_path: Path, port: int, attempts: int = 3) -> tuple[str, str]:
    """Host-side: HTTPS qua Burp với CA vừa cài (stdlib + retry)."""
    import http.client
    import ssl
    import time

    last_err = ""
    for attempt in range(attempts):
        ctx = ssl.create_default_context(cafile=str(pem_path))
        conn = http.client.HTTPSConnection("127.0.0.1", port, context=ctx, timeout=30)
        try:
            conn.set_tunnel("example.com", 443)
            conn.request("GET", "/", headers={"Host": "example.com"})
            resp = conn.getresponse()
            resp.read()
            return str(resp.status), ""
        except (OSError, ssl.SSLError) as e:
            last_err = str(e)
            if attempt < attempts - 1:
                time.sleep(2)
        finally:
            conn.close()
    return "000", last_err


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
    magisk_present = staticmethod(magisk_present)
    integrity_status = staticmethod(integrity_status)

    @staticmethod
    def _frida_start_default(adb, cfg):
        return frida_server.frida_start(
            adb, Path(cfg.tools_dir) / "frida-server.xz", alias=cfg.frida_alias)

    frida_start = staticmethod(_frida_start_default)
    frida_health = staticmethod(
        lambda adb: frida_server._wait_frida_ps(adb, tries=3, delay=1.0))
    unpin_smoke = staticmethod(
        lambda adb, cfg: frida_scripts.run_unpin("com.android.chrome", None,
                                                 timeout=60))


def run_p1(cfg, deps: Deps | None = None) -> tuple[bool, list[tuple[str, bool, str]]]:
    """Chạy chuỗi bước P1; ok chỉ True khi MỌI bước then chốt xanh."""
    d = deps or Deps()
    rows: list[tuple[str, bool, str]] = []

    def step(name, fn, *a):
        try:
            detail = fn(*a)
        except Exception as e:  # noqa: BLE001 — selftest tổng hợp mọi lỗi
            rows.append((name, False, str(e)[:300]))
            return False
        ok = detail is not False  # None = side-effect ok; False = fail tường minh
        rows.append((name, ok, "ok" if detail is None or detail is True
                     else str(detail)[:300]))
        return ok

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

    def _do_ca():
        der = d.fetch_der(cfg.proxy_port)
        pem, name = cert_mod.pem_and_name(der)
        pem_path = ws / "_shared" / "burp-ca" / name
        pem_path.parent.mkdir(parents=True, exist_ok=True)
        pem_path.write_text(pem, encoding="ascii")
        return d.install_system_ca(der, adb)

    if not step("ca", _do_ca):
        return False, rows
    pem_files = sorted((ws / "_shared" / "burp-ca").glob("*.0"))
    code, err = d.host_verify(pem_files[-1], cfg.proxy_port)
    ca_host_ok = code == "200"
    rows.append(("ca-host", ca_host_ok, f"code={code} {err}".strip()[:300]))
    if not ca_host_ok:
        return False, rows

    proxy_ok = step("proxy-on", d.proxy_on, adb, cfg.proxy_port)
    if not proxy_ok:
        return False, rows
    route_ok = d.device_route_probe(adb, cfg.proxy_port)
    rows.append(("device-route", route_ok,
                 "CONNECT qua proxy" if route_ok else "nc CONNECT khong thay 200"))
    if not route_ok:
        return False, rows

    dcode, derr = d.device_https_probe(adb, cfg.proxy_port)
    if dcode == "nocurl":
        rows.append(("https-probe", True,
                     "skipped (image khong co curl) — da chung minh bang nc + ca-host"))
        probe_ok = True
    else:
        probe_ok = dcode == "200"
        rows.append(("https-probe", probe_ok, f"code={dcode} {derr}".strip()[:300]))
    return probe_ok, rows


def run_p2(cfg, deps: "Deps | None" = None) -> tuple[bool, list]:
    """P2 = toàn bộ P1 + magisk + integrity stack + frida ẩn + unpin smoke."""
    d = deps or Deps()
    p1_ok, rows = run_p1(cfg, deps=d)  # chuyển deps xuống P1 (test/real)
    serial = d.avd_serial()
    adb = d.adb_factory(serial)

    if not d.magisk_present(adb):
        rows.append(("magisk", False, "chua root — chay: mph root install"))
        return False, rows
    rows.append(("magisk", True, "su -v ok"))

    try:
        st = d.integrity_status(adb, cfg)
        integ_ok = bool(st.get("shamiko")) and bool(st.get("pif"))
        rows.append(("integrity", integ_ok, json.dumps(st, default=str)[:300]))
    except Exception as e:  # noqa: BLE001
        rows.append(("integrity", False, str(e)[:300]))
        integ_ok = False

    try:
        remote = d.frida_start(adb, cfg)
        frida_ok = d.frida_health(adb)
        rows.append(("frida", frida_ok,
                     f"{remote} health={'ok' if frida_ok else 'fail'}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("frida", False, str(e)[:300]))
        frida_ok = False

    try:
        code, out = d.unpin_smoke(adb, cfg)
        rows.append(("unpin-smoke", True, f"exit={code} {out[:120]}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("unpin-smoke", False, str(e)[:300]))

    return p1_ok and integ_ok and frida_ok, rows
