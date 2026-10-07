"""Client MCP-stdio cho codebase-memory-mcp: index + status."""
import json
import subprocess
from pathlib import Path

from ..errors import HarnessError


def project_name(repo_path: Path) -> str:
    """Tên project theo quy ước codebase-memory (path flatten)."""
    s = str(Path(repo_path).resolve())
    for ch in ":\\/ .":
        s = s.replace(ch, "-")
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-")


class IndexClient:
    """Nói MCP stdio (JSON-RPC newline-delimited) với codebase-memory-mcp."""

    def __init__(self, cmd):
        self._cmd = list(cmd) if isinstance(cmd, (list, tuple)) else [cmd]
        self._id = 0
        self._proc = subprocess.Popen(
            self._cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
        self._call("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "mph", "version": "0.1"}})

    def _send(self, obj) -> None:
        try:
            self._proc.stdin.write(json.dumps(obj) + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise HarnessError("index server da chet (stdin)", hint=str(e)) from e

    def _read(self, want_id: int) -> dict:
        line = self._proc.stdout.readline()
        if not line:
            raise HarnessError(
                "index server EOF truoc response",
                hint=f"khong nhan duoc id={want_id} — server chet giua chung")
        try:
            msg = json.loads(line)
        except ValueError:
            return self._read(want_id)
        return msg

    def _call(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        body = {"jsonrpc": "2.0", "method": method, "id": self._id}
        if params is not None:
            body["params"] = params
        self._send(body)
        while True:
            msg = self._read(self._id)
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise HarnessError(f"index server error: {method}",
                                        hint=str(msg["error"]))
                return msg.get("result", {})

    def _tool(self, name: str, arguments: dict) -> dict:
        r = self._call("tools/call", {"name": name, "arguments": arguments})
        for part in (r.get("content") or []):
            if part.get("type") == "text":
                try:
                    return json.loads(part["text"])
                except ValueError:
                    return {"raw": part["text"]}
        return r

    def index_repo(self, repo_path: Path, mode: str = "moderate") -> dict:
        return self._tool("index_repository",
                          {"repo_path": str(Path(repo_path).resolve()),
                           "mode": mode})

    def status(self, project: str) -> dict:
        return self._tool("index_status", {"project": project})

    def close(self) -> None:
        try:
            self._proc.stdin.close()
            self._proc.wait(timeout=10)
        except OSError:
            pass


def ensure_indexed(cfg, jadx_out: Path) -> dict:
    """Index nếu status chưa ok (idempotent)."""
    c = IndexClient(cfg.index_cmd)
    try:
        proj = project_name(jadx_out)
        st = c.status(proj)
        if st.get("status") == "ok":
            return st
        return c.index_repo(jadx_out, getattr(cfg, "index_mode", "moderate"))
    finally:
        c.close()
