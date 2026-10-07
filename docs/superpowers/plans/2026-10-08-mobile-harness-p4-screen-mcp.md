# Mobile Pentest Harness — P4 Screen & MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho AI điều khiển emulator bằng mắt+ tay (screenshot → tọa độ → tap) qua **MCP server** + đo **Play Integrity verdict thật** (SPIC) — DoD `mph selftest --phase p4` xanh thêm 5 hàng.

**Architecture:** `mph/device/screen.py` (screencap binary-safe + wm-size meta + input + uiautomator), `mph/root/spic.py` (verdict), `mcp_server/server.py` (**MCP-stdio thuần stdlib**, đối xứng index client). Skills `mp-*` mỏng gọi CLI.

**Tech Stack:** Python 3.12 stdlib; adb; SPIC apk đã vendor (`tools/spic.apk`).

**Spec:** `docs/superpowers/specs/2026-10-07-mobile-pentest-harness-design.md` §4.1 screen, §6 MCP surface, §4.3 `mph integrity check`.

**Ruling:** fastmcp 2.14.4 **xung đột** với `mcp` pkg trong env (`streamable_http_client` ImportError) → MCP server **tự viết stdio JSON-RPC** (pattern đã chứng minh ở `mph/re/index.py`). Zero deps mới.

## Global Constraints

- Windows 11; idempotent; `HarnessError(msg, hint)`; file < 400 dòng; conventional commits; không deps mới.
- Screenshot phải **binary-safe** (PNG magic `\x89PNG`) — adb `exec-out` + bytes capture, không qua text pipe.
- Tọa độ: mọi API nhận tọa độ theo **màn hình thật** (wm size); meta kèm theo để client map scale ảnh.
- MCP server: mỗi message 1 dòng JSON; `initialize` → `notifications/initialized` → `tools/list` / `tools/call`.

## Review Focus

1. **Screencap corrupt do CRLF** (shell CR injection) — PNG magic phải được verify, sai → raise. Test: T2 `test_screenshot_rejects_corrupt`.
2. **`wm size` có Override size** (density scale) — phải lấy Override nếu có. Test: T1 `test_wm_size_prefers_override`.
3. **`input text` với khoảng trắng/ký tự đặc biệt** — escape `%s` cho space, từ chối ký tự control. Test: T1 `test_type_text_escapes`.
4. **MCP server nhận request khi đang chạy tool lâu** — đọc line loop, không chết khi 1 tool raise (trả isError). Test: T4 `test_server_survives_tool_error`.
5. **SPIC chưa từng mở (first-run dialog)** — verdict "NO_VERDICT" cấu trúc, không crash. Test: T3 `test_spic_no_verdict`.

---

### Task 1: Adb.run_raw + screen primitives

**Files:** Modify `mph/device/adb.py`; Create `mph/device/screen.py`; Test `tests/test_screen.py`

**Interfaces (Produces):** `Adb.run_raw(*args, timeout=60) -> tuple[int, bytes]`; `wm_size(adb) -> tuple[int, int]`; `tap(adb, x, y)`, `swipe(adb, x1, y1, x2, y2, ms=300)`, `type_text(adb, s)`, `key(adb, keycode)`.

- [ ] **Step 1 — failing tests:**

```python
# tests/test_screen.py
from mph.device.screen import key, swipe, tap, type_text, wm_size

class FakeAdb:
    def __init__(self, out="Physical size: 1080x2400\n"):
        self.out = out; self.calls = []
    def run(self, *args, timeout=60, device=True):
        self.calls.append(" ".join(args))
        return type("R", (), {"ok": True, "out": self.out, "err": "", "code": 0})()

def test_wm_size_basic():
    assert wm_size(FakeAdb()) == (1080, 2400)

def test_wm_size_prefers_override():
    a = FakeAdb("Physical size: 1080x2400\nOverride size: 720x1600\n")
    assert wm_size(a) == (720, 1600)

def test_tap_and_key():
    a = FakeAdb()
    tap(a, 540, 1200)
    key(a, "3")
    assert any("input tap 540 1200" in c for c in a.calls)
    assert any("input keyevent 3" in c for c in a.calls)

def test_swipe():
    a = FakeAdb()
    swipe(a, 100, 200, 300, 400, 250)
    assert any("input swipe 100 200 300 400 250" in c for c in a.calls)

def test_type_text_escapes():
    a = FakeAdb()
    type_text(a, "hello world")
    assert any("hello%sworld" in c for c in a.calls)

def test_type_text_rejects_control():
    import pytest
    from mph.errors import HarnessError
    with pytest.raises(HarnessError):
        type_text(FakeAdb(), "bad\nnewline")
```

- [ ] **Step 2 — FAIL** → **Step 3 — Implement:** `Adb.run_raw` giống `run` nhưng `text=False, capture bytes` (không retry riêng — caller tự loop nếu cần):

```python
# adb.py thêm
def run_raw(self, *args: str, timeout: float = 60) -> tuple[int, bytes]:
    cmd = [self.adb_path] + (["-s", self.serial] if self.serial else []) + list(args)
    p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return p.returncode, p.stdout
```

```python
# mph/device/screen.py
"""Điều khiển màn hình: tọa độ theo màn hình thật (wm size)."""
from ..errors import HarnessError


def wm_size(adb) -> tuple[int, int]:
    r = adb.run("shell", "wm", "size")
    phys = over = None
    for line in (r.out or "").splitlines():
        if line.startswith("Override size:"):
            over = line.split(":", 1)[1].strip()
        elif line.startswith("Physical size:"):
            phys = line.split(":", 1)[1].strip()
    raw = over or phys
    if not raw or "x" not in raw:
        raise HarnessError("khong doc duoc wm size", hint=r.out[:100])
    w, h = raw.lower().split("x", 1)
    return int(w), int(h)


def tap(adb, x: int, y: int) -> None:
    adb.run("shell", "input", "tap", str(int(x)), str(int(y)))


def swipe(adb, x1: int, y1: int, x2: int, y2: int, ms: int = 300) -> None:
    adb.run("shell", "input", "swipe",
            str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(ms)))


def type_text(adb, s: str) -> None:
    if any(ord(ch) < 32 or ch == '"' for ch in s):
        raise HarnessError("type_text ky tu khong ho tro",
                            hint="chi ASCII in duoc; dung key() cho dieu khien")
    adb.run("shell", "input", "text", s.replace(" ", "%s"))


def key(adb, keycode: str) -> None:
    adb.run("shell", "input", "keyevent", keycode)
```

- [ ] **Step 4 — PASS** → **Step 5 — Commit** `feat: adb run_raw + screen primitives`.

### Task 2: screenshot + ui_dump + find

**Files:** Modify `mph/device/screen.py`; Test `tests/test_screen.py` (thêm)

**Interfaces (Produces):** `screenshot(adb, dest: Path) -> dict` (meta `{"path", "screen": [w,h], "png_bytes"}`; verify magic `\x89PNG`); `ui_dump(adb, dest: Path) -> Path`; `find_bounds(xml: Path, text: str) -> tuple[int, int] | None` (center của node đầu có `text=` khớp).

- [ ] **Step 1 — failing tests (thêm):**

```python
def test_screenshot_writes_png(tmp_path, monkeypatch):
    import mph.device.screen as S
    png = b"\x89PNG\r\n\x1a\n" + b"FAKEDATA" * 10
    monkeypatch.setattr(S, "_screencap_raw", lambda adb: (0, png))
    dest = tmp_path / "s.png"
    meta = S.screenshot(FakeAdb(), dest)
    assert dest.read_bytes()[:4] == b"\x89PNG"
    assert meta["path"] == str(dest) and meta["screen"] == [1080, 2400]

def test_screenshot_rejects_corrupt(tmp_path, monkeypatch):
    import mph.device.screen as S
    monkeypatch.setattr(S, "_screencap_raw", lambda adb: (0, b"NOTPNG!!"))
    from mph.errors import HarnessError
    import pytest
    with pytest.raises(HarnessError):
        S.screenshot(FakeAdb(), tmp_path / "s.png")

def test_find_bounds_center(tmp_path):
    xml = tmp_path / "ui.xml"
    xml.write_text(
        '<hierarchy><node bounds="[100,200][300,400]" text="OK"/></hierarchy>',
        encoding="utf-8")
    assert S.find_bounds(xml, "OK") == (200, 300)
    assert S.find_bounds(xml, "NOPE") is None
```

- [ ] **Step 2 — FAIL** → **Step 3 — Implement (thêm vào screen.py):**

```python
import re as _re
from pathlib import Path

_PNG = b"\x89PNG"


def _screencap_raw(adb) -> tuple[int, bytes]:
    return adb.run_raw("exec-out", "screencap", "-p", timeout=30)


def screenshot(adb, dest: Path) -> dict:
    """Chụp PNG binary-safe + meta tọa độ (screen = kích thước thật)."""
    code, data = _screencap_raw(adb)
    if code != 0 or not data.startswith(_PNG):
        raise HarnessError("screencap that bai / khong phai PNG",
                            hint=f"code={code} bytes={len(data)}")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return {"path": str(dest), "screen": list(wm_size(adb)),
            "png_bytes": len(data)}


def ui_dump(adb, dest: Path) -> Path:
    adb.run("shell", "uiautomator", "dump", "/sdcard/ui.xml", timeout=30)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    p = adb.run("pull", "/sdcard/ui.xml", str(dest), timeout=30)
    if not p.ok or not dest.exists():
        raise HarnessError("uiautomator dump that bai", hint=p.err)
    return dest


_BOUNDS_RE = _re.compile(r'\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]')


def find_bounds(xml: Path, text: str) -> tuple[int, int] | None:
    """Center của node đầu có text khớp chính xác."""
    raw = Path(xml).read_text(encoding="utf-8", errors="replace")
    for m in _re.finditer(r"<node[^>]*>", raw):
        node = m.group(0)
        if f'text="{text}"' in node:
            b = _BOUNDS_RE.search(node)
            if b:
                x1, y1, x2, y2 = map(int, b.groups())
                return (x1 + x2) // 2, (y1 + y2) // 2
    return None
```

- [ ] **Step 4 — PASS** → **Step 5 — Commit** `feat: binary-safe screenshot + ui dump/find`.

### Task 3: SPIC integrity verdict

**Files:** Create `mph/root/spic.py`; Test `tests/test_spic.py`

**Interfaces (Produces):** `parse_verdict(ui_xml_text: str) -> str` (giá trị `"MEETS_BASIC"`/`"MEETS_DEVICE"`/`"MEETS_STRONG_INTEGRITY"`/`"NO_INTEGRITY"` đầu tiên xuất hiện, hoặc `"NO_VERDICT"`); `integrity_check(adb, cfg, ws: Path) -> dict` (install spic.apk nếu thiếu → launch → poll dump ×6 (sleep 3) → verdict + screenshot evidence → trả `{"verdict", "evidence"}`; **không** uninstall).

- [ ] **Step 1 — failing tests:**

```python
# tests/test_spic.py
from mph.root.spic import parse_verdict

def test_parse_basic():
    xml = '<node text="MEETS_BASIC_INTEGRITY"/><node text="anything"/>'
    assert parse_verdict(xml) == "MEETS_BASIC"

def test_parse_device_priority():
    xml = '<node text="MEETS_BASIC"/><node text="MEETS_DEVICE_INTEGRITY"/>'
    # MEETS_DEVICE mạnh hơn — nhưng lấy mốc xuất hiện đầu? Quy ước: lấy CAO NHẤT tìm được
    assert parse_verdict(xml) == "MEETS_DEVICE"

def test_parse_none():
    xml = '<node text="hello"/>'
    assert parse_verdict(xml) == "NO_VERDICT"
```

- [ ] **Step 2 — FAIL** → **Step 3 — Implement:**

```python
# mph/root/spic.py
"""Đo Play Integrity verdict thật bằng app SPIC + uiautomator."""
import time
from pathlib import Path

from ..device import screen
from ..errors import HarnessError

_LEVELS = ["MEETS_STRONG_INTEGRITY", "MEETS_DEVICE", "MEETS_BASIC"]
_PKG = "com.henrichs.spic"  # SPIC app package (herzhenr/spic-android)


def parse_verdict(ui_xml_text: str) -> str:
    """Trả mức CAO NHẤT tìm được trong dump; NO_VERDICT nếu không có."""
    best = None
    for lv in _LEVELS:
        if lv in ui_xml_text:
            best = lv
            break
    if best is None and "NO_INTEGRITY" in ui_xml_text:
        return "NO_INTEGRITY"
    return best or "NO_VERDICT"


def integrity_check(adb, cfg, ws: Path) -> dict:
    """Install (nếu thiếu) + mở SPIC + poll verdict; evidence screenshot."""
    have = adb.run("shell", "pm", "list", "packages")
    if _PKG not in (have.out or ""):
        apk = Path(cfg.tools_dir) / "spic.apk"
        if not apk.exists():
            raise HarnessError("thieu tools/spic.apk", hint="chay mph bootstrap")
        r = adb.run("install", "-r", str(apk), timeout=120)
        if not r.ok:
            raise HarnessError("cai SPIC that bai", hint=(r.out or "")[-200:])
    adb.run("shell", "am", "force-stop", _PKG)
    adb.run("shell", "am", "start", "-n", f"{_PKG}/MainActivity")
    ws = Path(ws)
    ws.mkdir(parents=True, exist_ok=True)
    verdict = "NO_VERDICT"
    dump = ws / "spic_ui.xml"
    for _ in range(6):
        time.sleep(3)
        try:
            screen.ui_dump(adb, dump)
            verdict = parse_verdict(dump.read_text(encoding="utf-8",
                                                   errors="replace"))
        except HarnessError:
            continue
        if verdict != "NO_VERDICT":
            break
    shot = ws / "spic_evidence.png"
    try:
        screen.screenshot(adb, shot)
    except HarnessError:
        shot = None
    return {"verdict": verdict,
            "evidence": str(shot) if shot else ""}
```

(SPK activity thực tế có thể khác `MainActivity` — integration step sẽ đọc `dumpsys package` để lấy launchable activity và sửa hằng số nếu cần; ghi ledger.)

- [ ] **Step 4 — PASS** → **Step 5 — Commit** `feat: spic integrity verdict`.

### Task 4: MCP-stdio server (stdlib)

**Files:** Create `mcp_server/__init__.py`, `mcp_server/server.py`; Test `tests/test_mcp_server.py`

**Interfaces (Produces):** `TOOLS: dict[str, callable]` (mỗi tool `(args: dict) -> dict`); `serve(stdin, stdout)` — loop JSON-lines; `main()` chạy stdin/stdout thật. Tools tối thiểu: `mph_doctor`, `mph_screenshot(dir)`, `mph_tap(x, y)`, `mph_swipe(x1,y1,x2,y2,ms)`, `mph_type(text)`, `mph_key(keycode)`, `mph_ui_find(text)` (dump + center), `mph_packages()`, `mph_integrity_check()`, `mph_selftest_phase()` (trả list hàng của phase hiện có nhanh: p1).

- [ ] **Step 1 — failing tests:**

```python
# tests/test_mcp_server.py
import io, json
from mcp_server.server import TOOLS, serve

def test_tools_registry_shape():
    assert len(TOOLS) >= 10
    for name in ("mph_screenshot", "mph_tap", "mph_ui_find"):
        assert name in TOOLS

def _run_serve(messages):
    inn = io.StringIO("".join(json.dumps(m) + "\n" for m in messages))
    out = io.StringIO()
    serve(inn, out)
    return [json.loads(l) for l in out.getvalue().splitlines() if l.strip()]

def test_serve_initialize_and_tools_list():
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    resp = _run_serve(msgs)
    by_id = {m.get("id"): m for m in resp}
    assert by_id[1]["result"]["protocolVersion"] == "2024-11-05"
    names = [t["name"] for t in by_id[2]["result"]["tools"]]
    assert "mph_tap" in names

def test_serve_survives_tool_error(monkeypatch):
    def boom(args): raise RuntimeError("boom")
    monkeypatch.setitem(__import__("mcp_server.server", fromlist=["TOOLS"]).TOOLS,
                        "mph_tap", boom)
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "mph_tap", "arguments": {"x": 1, "y": 2}}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
    ]
    resp = _run_serve(msgs)
    by_id = {m.get("id"): m for m in resp}
    assert by_id[2]["result"]["isError"] is True
    assert by_id[3]  # server còn sống
```

- [ ] **Step 2 — FAIL** → **Step 3 — Implement:**

```python
# mcp_server/server.py
"""MCP-stdio server thuần stdlib cho mph (đối xứng mph/re/index client).

Chạy: python -m mcp_server.server  (stdio, newline-delimited JSON)
Đăng ký vào Claude: .mcp.json {"mcpServers": {"mph": {
    "command": "python", "args": ["-m", "mcp_server.server"],
    "cwd": "<repo>"}}}
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mph.config import load_config                    # noqa: E402
from mph.device import screen as screen_mod           # noqa: E402
from mph.device import avd as avd_mod                 # noqa: E402
from mph.device.adb import Adb                        # noqa: E402
from mph.doctor import check_env, Probes              # noqa: E402
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
    rows = check_env(load_config(), Probes(devices=lambda: avd_mod.Adb and []))
    return {"rows": [[n, ok, h] for n, ok, h in rows]}


def t_screenshot(args):
    dest = _ws() / "shots" / "screen.png"
    import time
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

_SCHEMAS = {  # mô tả tối giản cho tools/list
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
                    "content": [{"type": "text", "text": f"no tool {name}"}]}})
                continue
            try:
                result = fn(args)
                _reply(stdout, {"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text",
                                 "text": json.dumps(result, ensure_ascii=False,
                                                    default=str)}]}})
            except Exception as e:  # noqa: BLE001 — isError cho client
                _reply(stdout, {"jsonrpc": "2.0", "id": mid, "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": str(e)[:500]}]}})


def _reply(stdout, obj) -> None:
    stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    stdout.flush()


def main() -> None:
    serve(sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4 — PASS** → **Step 5 — Commit** `feat: stdlib mcp-stdio server (10 tools)`.

### Task 5: Skills mp-* + .mcp.json

**Files:** Create `skills/mp-setup/SKILL.md`, `skills/mp-recon/SKILL.md`, `skills/mp-traffic/SKILL.md`, `skills/mp-audit/SKILL.md`, `.mcp.json`; Test `tests/test_skills.py`

**Interfaces (Produces):** 4 skill docs + MCP registration file.

- [ ] **Step 1 — failing test:**

```python
# tests/test_skills.py
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

def test_skills_exist_with_frontmatter():
    for name in ("mp-setup", "mp-recon", "mp-traffic", "mp-audit"):
        f = REPO / "skills" / name / "SKILL.md"
        assert f.exists(), name
        head = f.read_text(encoding="utf-8")[:200]
        assert head.startswith("---") and "name:" in head

def test_mcp_json_shape():
    import json
    d = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))
    assert "mph" in d["mcpServers"]
```

- [ ] **Step 2 — FAIL** → **Step 3 — Implement:** mỗi SKILL.md dạng:

```markdown
---
name: mp-setup
description: Dựng/trạng thái môi trường pentest mobile (emulator, root, frida, proxy) — dùng khi cần chuẩn bị hoặc kiểm tra thiết bị trước audit.
---

# mp-setup

Chạy tuần tự (PowerShell, cwd = repo mobile-harness):

1. `python -c "import sys; sys.argv=['mph','doctor']; from mph.cli import app; app()"` — mọi hàng phải OK.
2. `mph setup run` — bootstrap + AVD + adb root (idempotent).
3. `mph root install` — Magisk + integrity stack (cần emulator TẮT).
4. `mph frida start` — frida-server ẩn (sysmondd).
5. `mph burp start` + `mph proxy on` + `mph cert` — traffic qua Burp 8082.
6. `mph selftest --phase p2` — cổng xanh thì môi trường sẵn sàng.

Xem spec: docs/superpowers/specs/2026-10-07-mobile-pentest-harness-design.md
```

(mp-recon: pull/jadx/manifest/index + câu hỏi codebase-memory gợi ý; mp-traffic: proxy on + burp history qua MCP 9876 + unpin; mp-audit: walkthrough 4-pass + findings format — chi tiết đầy đủ viết lúc P5, bản này outline đúng cấu trúc frontmatter.)

`.mcp.json`:

```json
{
  "mcpServers": {
    "mph": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "C:\\Users\\sonnt\\Documents\\Mobile\\mobile-harness"
    }
  }
}
```

- [ ] **Step 4 — PASS** → **Step 5 — Commit** `feat: skills mp-* + mcp registration`.

### Task 6: CLI (screen + integrity check) + selftest p4

**Files:** Modify `mph/cli.py`, `mph/selftest.py`; Test `tests/test_cli.py`, `tests/test_selftest.py`

**Interfaces (Produces):** CLI `mph screen {screenshot|tap|swipe|type|key|ui}`, `mph integrity check`; `run_p4(cfg, deps)` thêm hàng: `wm-size`, `screenshot`, `ui-dump`, `tap-smoke` (HOME key + tap giữa màn hình), `spic-verdict` (verdict parse được — bất kỳ giá trị nào kể cả NO_VERDICT đều OK hàng này, verdict hiển thị).

- [ ] **Step 1 — failing tests:** test_cli thêm `("screen", "integrity")` vào help-check; test_selftest thêm `test_p4_green` (DepsP4 kế thừa DepsP3-style, thêm wm_size/screenshot/ui_dump/tap/spic fakes; assert names chứa 5 hàng mới + ok True).

- [ ] **Step 2 — FAIL** → **Step 3 — Implement:** CLI groups như pattern cũ; `run_p4` nối `run_p3` + 5 bước dùng `screen_mod` và `spic_mod.integrity_check` (Deps thêm `wm_size, screenshot, ui_dump, tap_smoke, spic_check` mặc định nối module; tap_smoke = key HOME + tap center từ wm_size).

- [ ] **Step 4 — PASS** → **Step 5 — Integration (cổng P4):**
  1. `mph screen screenshot` → PNG mở được + meta
  2. `mph screen ui` + `mph screen tap X Y` (HOME trước)
  3. `mph integrity check` — verdict SPIC thật (sửa activity nếu launch sai, ghi ledger)
  4. `python -m mcp_server.server` smoke qua pipe (initialize + tools/list)
  5. `mph selftest --phase p4` exit 0 × 2 lần
- [ ] **Step 6 — Commit** `feat: p4 screen/mcp/skills + selftest p4`.

## Self-review
- Spec §4.1 screen ✓ (screencap/tap/swipe/text/uiautomator/scrcpy-optional bỏ — P5 nếu cần), §6 MCP surface ✓ (10 tools + registry file), §4.3 `integrity check` ✓ (SPIC), §4.4 skills ✓.
- F6/F7 deferred từ P3 không tái xuất hiện trong scope này (stdio server mới đã có loop + isError).
- Types khớp xuyên suốt (đã đối chiếu).
- Review Focus 5/5 có test owner.
