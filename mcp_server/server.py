"""MCP-stdio server thuần stdlib cho mph (đối xứng mph/re/index client).

Chạy: python -m mcp_server.server  (stdio, newline-delimited JSON)
Đăng ký vào Claude qua .mcp.json ở repo root.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mph.config import load_config                    # noqa: E402
from mph.device import screen as screen_mod           # noqa: E402
from mph.device import avd as avd_mod                 # noqa: E402
from mph.device.adb import Adb                        # noqa: E402
from mph.doctor import Probes, check_env              # noqa: E402
from mph.re import apks as apks_mod                   # noqa: E402
from mph.root import spic as spic_mod                 # noqa: E402
from mph.selftest import run_p1                       # noqa: E402


def _adb():
    cfg = load_config()
    serial = avd_mod.avd_serial(cfg.avd_name)
    return Adb(serial=serial) if serial else Adb()


def _ws():
    return Path(load_config().workspace) / "_shared"


def t_doctor(args):
    rows = check_env(load_config(), Probes(devices=lambda: []))
    return {"rows": [[n, ok, h] for n, ok, h in rows]}


def t_screenshot(args):
    dest = _ws() / "shots" / f"screen-{time.strftime('%H%M%S')}.png"
    return screen_mod.screenshot(_adb(), dest)


def t_tap(args):
    screen_mod.tap(_adb(), args["x"], args["y"])
    return {"ok": True}


def t_swipe(args):
    screen_mod.swipe(_adb(), args["x1"], args["y1"], args["x2"],
                     args["y2"], args.get("ms", 300))
    return {"ok": True}


def t_type(args):
    screen_mod.type_text(_adb(), args["text"])
    return {"ok": True}


def t_key(args):
    screen_mod.key(_adb(), args["keycode"])
    return {"ok": True}


def t_ui_find(args):
    adb = _adb()
    dump = _ws() / "ui.xml"
    screen_mod.ui_dump(adb, dump)
    center = screen_mod.find_bounds(dump, args["text"])
    return {"center": center, "dump": str(dump)}


def t_packages(args):
    return {"packages": apks_mod.list_packages(_adb())}


def t_integrity_check(args):
    cfg = load_config()
    return spic_mod.integrity_check(_adb(), cfg, _ws() / "spic")


def t_selftest_phase(args):
    ok, rows = run_p1(load_config())
    return {"ok": ok, "rows": [[n, o, d[:120]] for n, o, d in rows]}


TOOLS = {
    "mph_doctor": t_doctor,
    "mph_screenshot": t_screenshot,
    "mph_tap": t_tap,
    "mph_swipe": t_swipe,
    "mph_type": t_type,
    "mph_key": t_key,
    "mph_ui_find": t_ui_find,
    "mph_packages": t_packages,
    "mph_integrity_check": t_integrity_check,
    "mph_selftest_phase": t_selftest_phase,
}

_SCHEMAS = {
    "mph_screenshot": {"type": "object", "properties": {}},
    "mph_tap": {"type": "object", "properties": {
        "x": {"type": "integer"}, "y": {"type": "integer"}},
        "required": ["x", "y"]},
    "mph_swipe": {"type": "object", "properties": {
        "x1": {"type": "integer"}, "y1": {"type": "integer"},
        "x2": {"type": "integer"}, "y2": {"type": "integer"},
        "ms": {"type": "integer"}}},
    "mph_type": {"type": "object", "properties": {
        "text": {"type": "string"}}, "required": ["text"]},
    "mph_key": {"type": "object", "properties": {
        "keycode": {"type": "string"}}, "required": ["keycode"]},
    "mph_ui_find": {"type": "object", "properties": {
        "text": {"type": "string"}}, "required": ["text"]},
}


def serve(stdin, stdout) -> None:
    """Loop JSON-lines; tool raise → isError, server sống tiếp."""
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        mid = msg.get("id")
        method = msg.get("method")
        if method == "initialize":
            _reply(stdout, {"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mph", "version": "0.1"}}})
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            tools = [{"name": n, "description": n,
                      "inputSchema": _SCHEMAS.get(n, {"type": "object"})}
                     for n in TOOLS]
            _reply(stdout, {"jsonrpc": "2.0", "id": mid,
                            "result": {"tools": tools}})
        elif method == "tools/call":
            name = (msg.get("params") or {}).get("name")
            args = (msg.get("params") or {}).get("arguments") or {}
            fn = TOOLS.get(name)
            if fn is None:
                _reply(stdout, {"jsonrpc": "2.0", "id": mid, "result": {
                    "isError": True,
                    "content": [{"type": "text",
                                 "text": f"no tool {name}"}]}})
                continue
            try:
                result = fn(args)
                _reply(stdout, {"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text",
                                 "text": json.dumps(result,
                                                    ensure_ascii=False,
                                                    default=str)}]}})
            except Exception as e:  # noqa: BLE001 — isError cho client
                _reply(stdout, {"jsonrpc": "2.0", "id": mid, "result": {
                    "isError": True,
                    "content": [{"type": "text",
                                 "text": str(e)[:500]}]}})


def _reply(stdout, obj) -> None:
    stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    stdout.flush()


def main() -> None:
    serve(sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
