# tests/test_burp_mcp.py
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from mph.errors import HarnessError
from mph.proxy.burp_mcp import BurpMcp

class Stub(BaseHTTPRequestHandler):
    """Stub MCP tối giản: /sse phát endpoint rồi đóng; response qua body POST.

    Không giữ connection nào mở — tránh reset loopback đa luồng trên Windows.
    Client thật đọc body trước khi chờ SSE nên hành vi này tương thích.
    """

    def do_GET(self):
        if self.path == "/sse":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(b"event: endpoint\ndata: /mcp?sessionId=abc\n\n")

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        resp = {"jsonrpc": "2.0", "id": body.get("id")}
        if body["method"] == "initialize":
            resp["result"] = {"protocolVersion": "2024-11-05"}
        elif body["method"] == "tools/list":
            resp["result"] = {"tools": [{"name": "project_options_get"}]}
        elif body["method"] == "tools/call":
            resp["result"] = {"content": [{"type": "text", "text": "{}"}]}
        data = json.dumps(resp).encode()
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

@pytest.fixture()
def stub_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()

def test_call_roundtrip(stub_server):
    r = BurpMcp(stub_server).call("project_options_get", {})
    assert "content" in r  # call() trả về result của tool, không bọc "result"

def test_tools_list(stub_server):
    assert "project_options_get" in BurpMcp(stub_server).tools()

def test_no_endpoint_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)  # không SSE
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    try:
        with pytest.raises(HarnessError):
            BurpMcp(port).call("x", {}, timeout=1.5)
    finally:
        srv.shutdown()

class _BodyResp:
    def __init__(self, obj):
        self._data = json.dumps(obj).encode()
    def read(self):
        return self._data
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False

class _SseResp:
    def __init__(self, lines):
        self._data = ("\n\n".join(lines) + "\n\n").encode()
    def __iter__(self):
        return iter(self._data.splitlines(keepends=True))
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False

def _body_resp(obj):
    return _BodyResp(obj)

def _sse_resp(lines):
    return _SseResp(lines)

def _url_of(u):
    return getattr(u, "full_url", str(u))

def test_rpc_error_surfaced(monkeypatch):
    import mph.proxy.burp_mcp as M
    monkeypatch.setattr(M.time, "sleep", lambda s: None)
    calls = []
    def fake_urlopen(url, timeout=None, **kw):
        calls.append(url)
        if "/sse" in _url_of(url):
            return _sse_resp(["event: endpoint", "data: /mcp?sid=1"])
        return _body_resp({"jsonrpc": "2.0", "id": 1,
                           "error": {"code": -32000, "message": "boom"}})
    monkeypatch.setattr(M.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(HarnessError) as e:
        BurpMcp(9999).call("some_tool", {})
    assert "boom" in str(e.value)

def test_sse_reader_reconnects(monkeypatch):
    import mph.proxy.burp_mcp as M
    monkeypatch.setattr(M.time, "sleep", lambda s: None)
    n = []
    def fake_urlopen(url, timeout=None, **kw):
        n.append(url)
        if "/sse" in _url_of(url):
            if len(n) < 3:            # 2 lần đầu Burp chưa mở port
                raise OSError("refused")
            return _sse_resp(["event: endpoint", "data: /mcp?sid=1"])
        return _body_resp({"jsonrpc": "2.0", "id": 1,
                           "result": {"content": [{"type": "text", "text": "{}"}]}})
    monkeypatch.setattr(M.urllib.request, "urlopen", fake_urlopen)
    r = BurpMcp(9999).call("project_options_get", {})
    assert "content" in r and len(n) >= 4  # GET×3 (2 fail) + POST×1
