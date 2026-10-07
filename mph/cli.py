"""CLI chính của mph — các group lệnh được thêm dần theo task."""
import typer

from .config import load_config
from .device.adb import Adb
from .doctor import Probes, check_env

app = typer.Typer(help="Mobile Pentest Harness", no_args_is_help=True)


@app.callback()
def _root() -> None:
    """mph — Mobile Pentest Harness."""


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
