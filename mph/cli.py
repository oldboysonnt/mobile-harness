"""CLI chính của mph — các group lệnh được thêm dần theo task."""
import json as _json
import socket
from pathlib import Path

import typer

from .bootstrap import create_avd, ensure_cmdline_tools, install_image
from .config import load_config
from .device import avd as avd_mod
from .device.adb import Adb
from .doctor import Probes, check_env
from .proxy import burp as burp_mod
from .proxy import cert as cert_mod
from .proxy import route as route_mod

app = typer.Typer(help="Mobile Pentest Harness", no_args_is_help=True)


@app.callback()
def _root() -> None:
    """mph — Mobile Pentest Harness."""


def _load_config():
    return load_config()


setup_app = typer.Typer(help="Bootstrap SDK/AVD va boot")
burp_app = typer.Typer(help="Dieu khien Burp Suite")
proxy_app = typer.Typer(help="Route traffic device qua Burp")
app.add_typer(setup_app, name="setup")
app.add_typer(burp_app, name="burp")
app.add_typer(proxy_app, name="proxy")


@app.command()
def doctor() -> None:
    """Kiem tra moi thanh phan moi truong can cho harness."""
    rows = check_env(load_config(), Probes(devices=lambda: Adb.devices()))
    bad = 0
    for name, ok, hint in rows:
        mark = "OK " if ok else "FAIL"
        print(f"[{mark}] {name}" + ("" if ok else f" — {hint}"))
        bad += 0 if ok else 1
    raise typer.Exit(code=1 if bad else 0)


@setup_app.command("run")
def setup_run() -> None:
    """Bootstrap cmdline-tools + image, tao/boot AVD, adb root (idempotent)."""
    cfg = _load_config()
    sdk = Path(cfg.sdk)
    if not (sdk / "cmdline-tools" / "latest" / "bin" / "sdkmanager.bat").exists():
        ensure_cmdline_tools(sdk, Path("tools") / "cache")
    install_image(sdk, cfg.image)
    create_avd(sdk, cfg.avd_name, cfg.image)
    avd_mod.avd_boot(sdk, cfg.avd_name)
    serial = avd_mod.avd_serial()
    if not serial:
        raise typer.Exit("khong thay emulator serial sau boot", code=1)
    adb = Adb(serial=serial)
    if not avd_mod.wait_booted(serial, adb):
        raise typer.Exit("timeout cho boot (300s)", code=1)
    adb.run("root")
    print(f"ready: {serial}")


@burp_app.command("start")
def burp_start_cmd() -> None:
    """Khoi dong Burp voi listener 8080 (idempotent)."""
    cfg = _load_config()
    pf = Path(cfg.workspace) / "_shared" / "burp" / "main.burp"
    pid = burp_mod.burp_start(cfg, pf, pf.with_suffix(".json"))
    print("burp running" if pid == -1 else f"burp pid={pid}")


@burp_app.command("status")
def burp_status_cmd() -> None:
    """In trang thai port listener cua Burp."""
    cfg = _load_config()
    with socket.socket() as s:
        s.settimeout(1.0)
        up = s.connect_ex(("127.0.0.1", cfg.proxy_port)) == 0
    print("running" if up else "not running")


@proxy_app.command("on")
def proxy_on_cmd() -> None:
    """Bat adb reverse + global http_proxy."""
    cfg = _load_config()
    serial = avd_mod.avd_serial()
    adb = Adb(serial=serial) if serial else Adb()
    route_mod.proxy_on(adb, cfg.proxy_port)
    print("proxy on")


@proxy_app.command("off")
def proxy_off_cmd() -> None:
    """Don sach reverse + http_proxy."""
    serial = avd_mod.avd_serial()
    adb = Adb(serial=serial) if serial else Adb()
    route_mod.proxy_off(adb)
    print("proxy off")


@app.command()
def cert(serial: str | None = None) -> None:
    """Tai CA Burp va cai vao system store cua device."""
    cfg = _load_config()
    der = cert_mod.fetch_der(cfg.proxy_port)
    adb = Adb(serial=serial) if serial else Adb()
    name = cert_mod.install_system_ca(der, adb)
    print(f"installed {name}")


@app.command()
def selftest(phase: str = typer.Option("p1", help="p1 = den HTTPS qua Burp")) -> None:
    """Chay kiem tra tich hợp end-to-end."""
    from .selftest import run_p1

    cfg = _load_config()
    ok, rows = run_p1(cfg)
    for name, good, detail in rows:
        print(f"[{'OK ' if good else 'FAIL'}] {name}: {detail}")
    raise typer.Exit(code=0 if ok else 1)
