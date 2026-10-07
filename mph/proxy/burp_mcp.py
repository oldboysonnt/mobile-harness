"""Client MCP native của Burp (SSE + JSON-RPC, port 9876).

Chuyển thể từ prior art Downloads/friendkit_analysis/burp_mcp.py thành class
có timeout cấu trúc (không treo khi Burp chưa bật MCP).
"""
import json
import queue
import threading
import time
import urllib.request

from ..errors import HarnessError


class BurpMcp:
    """Nói chuyện với MCP server built-in của Burp Pro."""

    def __init__(self, port: int) -> None:
        self.base = f"http://127.0.0.1:{port}"
        self.events: queue.Queue = queue.Queue()
        self._endpoint: str | None = None
        self._id = 0
        threading.Thread(target=self._sse_reader, daemon=True).start()

    def _sse_reader(self) -> None:
        resp = None
        for _ in range(3):  # Burp có thể mở port trễ — thử lại
            req = urllib.request.Request(
                self.base + "/sse", headers={"Accept": "text/event-stream"}
            )
            try:
                resp = urllib.request.urlopen(req, timeout=120)
                break
            except OSError:
                time.sleep(1.0)
        if resp is None:
            return
        ev, data = None, []
        for raw in resp:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
            elif line == "" and (ev or data):
                self.events.put((ev, "\n".join(data)))
                ev, data = None, []

    def _wait_endpoint(self, timeout: float) -> str:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._endpoint:
                return self._endpoint
            try:
                ev, data = self.events.get(timeout=1.0)
            except queue.Empty:
                continue
            if ev == "endpoint":
                self._endpoint = data
                return data
        raise HarnessError(
            "burp mcp khong phan hoi (khong co endpoint event)",
            hint="bat MCP trong Burp (port 9876) roi chay lai",
        )

    def _call(self, method: str, params: dict | None, timeout: float) -> dict:
        ep = self._wait_endpoint(timeout)
        self._id += 1
        body: dict = {"jsonrpc": "2.0", "method": method, "id": self._id}
        if params is not None:
            body["params"] = params
        req = urllib.request.Request(
            self.base + ep,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            raw = urllib.request.urlopen(req, timeout=timeout).read()
        except OSError:
            # Windows thỉnh thoảng reset loopback POST (AV/backlog) — thử lại 1 lần
            time.sleep(0.3)
            try:
                raw = urllib.request.urlopen(req, timeout=timeout).read()
            except OSError as e:
                raise HarnessError(f"burp mcp loi post: {method}", hint=str(e)) from e
        # JSON-RPC over HTTP: response có thể về ngay trong body (một số server),
        # hoặc qua SSE stream như Montague của Burp (202 + body rỗng).
        if raw:
            try:
                msg = json.loads(raw)
                if msg.get("id") == self._id:
                    self._raise_on_error(msg)
                    return msg
            except ValueError:
                pass
        stash: list[tuple[str, str]] = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                ev, data = self.events.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                msg = json.loads(data)
            except ValueError:
                continue
            if msg.get("id") == self._id:
                for s in stash:
                    self.events.put(s)
                self._raise_on_error(msg)
                return msg
            stash.append((ev, data))
        for s in stash:
            self.events.put(s)
        raise HarnessError(f"burp mcp timeout: {method}", hint="kiem tra Burp con chay")

    @staticmethod
    def _raise_on_error(msg: dict) -> None:
        if isinstance(msg.get("error"), dict):
            raise HarnessError(
                f"burp mcp error: {msg['error'].get('message', msg['error'])}",
                hint=f"code={msg['error'].get('code')}",
            )

    def call(self, tool: str, arguments: dict, timeout: float = 30.0) -> dict:
        """Gọi một MCP tool của Burp, trả result."""
        r = self._call("tools/call", {"name": tool, "arguments": arguments}, timeout)
        return r.get("result", r)

    def tools(self) -> list[str]:
        """Liệt kê tên các MCP tool Burp đang expose."""
        r = self._call("tools/list", None, 30.0)
        return [t.get("name", "") for t in r.get("result", {}).get("tools", [])]
