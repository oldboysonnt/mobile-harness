# tests/test_mcp_server.py
import io
import json

from mcp_server.server import TOOLS, serve

def test_tools_registry_shape():
    assert len(TOOLS) >= 10
    for name in ("mph_screenshot", "mph_tap", "mph_ui_find"):
        assert name in TOOLS

def _run_serve(messages):
    inn = io.StringIO("".join(json.dumps(m) + "\n" for m in messages))
    out = io.StringIO()
    serve(inn, out)
    return [json.loads(line) for line in out.getvalue().splitlines() if line.strip()]

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
    import mcp_server.server as S

    def boom(args):
        raise RuntimeError("boom")

    monkeypatch.setitem(S.TOOLS, "mph_tap", boom)
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
