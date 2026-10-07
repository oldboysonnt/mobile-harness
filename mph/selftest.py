"""Selftest P1: boot → burp → CA → proxy → HTTPS 200 qua Burp từ device."""
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
        return "nocurl", "device thieu curl — dung image google_apis API 34 hoac push curl"
    r = adb.run(
        "shell",
        f"curl -sx http://127.0.0.1:{port} -o /dev/null -w %{{http_code}} https://example.com",
        timeout=60,
    )
    return r.out.strip() or "000", r.err.strip()


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
    step("proxy-on", d.proxy_on, adb, cfg.proxy_port)
    code, err = d.device_https_probe(adb, cfg.proxy_port)
    ok = code == "200"
    rows.append(("https-probe", ok, f"code={code} {err}".strip()))
    return ok, rows
