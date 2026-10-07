"""CLI chính của mph — các group lệnh được thêm dần theo task."""
import json
import socket
from pathlib import Path

import typer

from .bootstrap import create_avd, ensure_cmdline_tools, install_image
from .config import load_config
from .device import avd as avd_mod
from .device.adb import Adb
from .doctor import Probes, check_env
from .frida import scripts as frida_scripts
from .frida.server import frida_start as frida_server_start
from .frida.server import frida_stop as frida_server_stop
from .proxy import burp as burp_mod
from .proxy import cert as cert_mod
from .proxy import route as route_mod
from .root.brutdroid import brutdroid_vendor
from .root.integrity import fingerprint_use, integrity_install, integrity_status
from .root.rootavd import root_via_rootavd
from .vendor import vendor_all

app = typer.Typer(help="Mobile Pentest Harness", no_args_is_help=True)


@app.callback()
def _root() -> None:
    """mph — Mobile Pentest Harness."""


def _load_config():
    return load_config()


setup_app = typer.Typer(help="Bootstrap SDK/AVD va boot")
burp_app = typer.Typer(help="Dieu khien Burp Suite")
proxy_app = typer.Typer(help="Route traffic device qua Burp")
root_app = typer.Typer(help="Magisk root + integrity stack")
frida_app = typer.Typer(help="Frida server + scripts")
integrity_app = typer.Typer(help="Play Integrity stack")
app.add_typer(setup_app, name="setup")
app.add_typer(burp_app, name="burp")
app.add_typer(proxy_app, name="proxy")
app.add_typer(root_app, name="root")
app.add_typer(frida_app, name="frida")
app.add_typer(integrity_app, name="integrity")


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
    avd_mod.avd_boot(sdk, cfg.avd_name,
                     log_path=Path(cfg.workspace) / "logs" / "emulator.log")
    serial = avd_mod.wait_serial(timeout=120, avd_name=cfg.avd_name)
    if not serial:
        print("khong thay emulator serial sau 120s — xem workspace/logs/emulator.log")
        raise typer.Exit(code=1)
    adb = Adb(serial=serial)
    if not avd_mod.wait_booted(serial, adb):
        print("timeout cho boot (300s)")
        raise typer.Exit(code=1)
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
    serial = avd_mod.avd_serial(cfg.avd_name)
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
    adb = Adb(serial=serial) if serial else Adb(serial=avd_mod.avd_serial(cfg.avd_name))
    name = cert_mod.install_system_ca(der, adb)
    print(f"installed {name}")


@app.command()
def selftest(phase: str = typer.Option("p1", help="p1 = HTTPS qua Burp; p2 = + magisk/integrity/frida")) -> None:
    """Chay kiem tra tich hợp end-to-end."""
    from .selftest import run_p1, run_p2

    cfg = _load_config()
    if phase == "p2":
        ok, rows = run_p2(cfg)
    else:
        ok, rows = run_p1(cfg)
    for name, good, detail in rows:
        print(f"[{'OK ' if good else 'FAIL'}] {name}: {detail}")
    raise typer.Exit(code=0 if ok else 1)


@app.command()
def bootstrap() -> None:
    """Tai/pin moi artifact ngoai (magisk, shamiko, pif, strongr, spic, rootavd, brutdroid)."""
    cfg = _load_config()
    paths = vendor_all(cfg)
    bd = brutdroid_vendor(Path(cfg.tools_dir) / "vendor" / "BrutDroid")
    print("vendored:", ", ".join(paths), "+", bd.name)


@root_app.command("install")
def root_install() -> None:
    """rootAVD patch Magisk + cai integrity stack (can emulator DANG TAT)."""
    cfg = _load_config()
    serial = avd_mod.avd_serial(cfg.avd_name)
    if serial:
        print("emulator dang chay — tat truoc khi root (patch ramdisk can AVD off)")
        raise typer.Exit(code=1)
    paths = vendor_all(cfg)
    root_via_rootavd(cfg, paths["rootavd"])
    avd_mod.avd_boot(Path(cfg.sdk), cfg.avd_name,
                     log_path=Path(cfg.workspace) / "logs" / "emulator.log")
    serial = avd_mod.wait_serial(timeout=180, avd_name=cfg.avd_name)
    if not serial or not avd_mod.wait_booted(serial, Adb(serial=serial)):
        print("boot lai sau root that bai")
        raise typer.Exit(code=1)
    adb = Adb(serial=serial)
    adb.run("root")
    print(json.dumps(integrity_install(adb, cfg, paths), default=str))


@root_app.command("status")
def root_status() -> None:
    serial = avd_mod.avd_serial()
    if not serial:
        print("khong co emulator")
        raise typer.Exit(code=1)
    print(json.dumps(integrity_status(Adb(serial=serial), _load_config()),
                     indent=2, default=str))


@frida_app.command("start")
def frida_start_cmd() -> None:
    cfg = _load_config()
    serial = avd_mod.avd_serial(cfg.avd_name)
    if not serial:
        print("khong co emulator — chay mph setup run")
        raise typer.Exit(code=1)
    paths = vendor_all(cfg)
    remote = frida_server_start(Adb(serial=serial), paths["frida-server"],
                                alias=cfg.frida_alias)
    print(f"frida server: {remote}")


@frida_app.command("stop")
def frida_stop_cmd() -> None:
    serial = avd_mod.avd_serial()
    frida_server_stop(Adb(serial=serial) if serial else Adb(),
                      _load_config().frida_alias)
    print("stopped")


@frida_app.command("unpin")
def frida_unpin_cmd(package: str) -> None:
    code, out = frida_scripts.run_unpin(package, None)
    print(f"unpin exit={code} {out[:200]}")


@integrity_app.command("status")
def integrity_status_cmd() -> None:
    serial = avd_mod.avd_serial()
    if not serial:
        print("khong co emulator")
        raise typer.Exit(code=1)
    print(json.dumps(integrity_status(Adb(serial=serial), _load_config()),
                     indent=2, default=str))


@integrity_app.command("use-fingerprint")
def integrity_use_cmd(name: str) -> None:
    serial = avd_mod.avd_serial()
    ok = fingerprint_use(Adb(serial=serial) if serial else Adb(),
                         _load_config(), name)
    print("applied" if ok else f"khong thay fingerprints/{name}.json")
