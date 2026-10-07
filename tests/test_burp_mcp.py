# tests/test_burp_mcp.py
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from mph.errors import HarnessError
from mph.proxy.burp_mcp import BurpMcp

class Stub(BaseHTTPRequestHandler):
    """Mô phỏng MCP của Burp: POST trả 202, response đẩy qua SSE stream."""

    def do_GET(self):
        if self.path == "/sse":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.server.sse_conn = self  # per-server, không dùng biến class
            self.wfile.write(b"event: endpoint\ndata: /mcp?sessionId=abc\n\n")
            self.wfile.flush()
            while True:  # giữ connection sống (thread daemon)
                time.sleep(0.2)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        resp = {"jsonrpc": "2.0", "id": body.get("id")}
        if body["method"] == "initialize":
            resp["result"] = {"protocolVersion": "2024-11-05"}
        elif body["method"] == "tools/list":
            resp["result"] = {"tools": [{"name": "project_options_get"}]}
        elif body["method"] == "tools/call":
            resp["result"] = {"content": [{"type": "text", "text": "{}"}]}
        self.send_response(202)
        self.end_headers()
        self.server.sse_conn.wfile.write(
            f"event: message\ndata: {json.dumps(resp)}\n\n".encode()
        )
        self.server.sse_conn.wfile.flush()

    def log_message(self, *a):
        pass

@pytest.fixture()
def stub_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    srv.sse_conn = None
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
