# tests/test_index.py
import sys
from pathlib import Path

import pytest

from mph.errors import HarnessError
from mph.re.index import IndexClient, ensure_indexed, project_name

FAKE = str(Path(__file__).parent / "fixtures" / "fake_mcp_index.py")
CMD = [sys.executable, FAKE]

def test_project_name_shape(tmp_path):
    p = project_name(tmp_path / "jadx-out")
    assert "jadx-out" in p and ":" not in p and "\\" not in p

def test_index_and_status_roundtrip(tmp_path):
    c = IndexClient(CMD)
    try:
        r = c.index_repo(tmp_path)
        assert r.get("status") == "ok"
        s = c.status(project_name(tmp_path))
        assert s.get("nodes") == 100
    finally:
        c.close()

def test_index_server_dies(tmp_path):
    dying = str(Path(__file__).parent / "fixtures" / "fake_dying.py")
    with pytest.raises(HarnessError) as e:
        IndexClient([sys.executable, dying]).index_repo(tmp_path)
    assert "index server" in str(e.value).lower() or "EOF" in str(e.value)

def test_ensure_indexed_skips_when_ok(tmp_path):
    calls = []
    class FakeClient:
        def __init__(self, cmd):
            pass
        def status(self, project):
            return {"status": "ok", "nodes": 5}
        def index_repo(self, repo, mode="moderate"):
            calls.append(repo)
            return {"status": "ok"}
        def close(self):
            pass
    import mph.re.index as I
    orig = I.IndexClient
    I.IndexClient = FakeClient
    try:
        class C:
            index_cmd = CMD
            index_mode = "moderate"
        got = ensure_indexed(C(), tmp_path)
        assert got["status"] == "ok" and calls == []  # đã ok → skip
    finally:
        I.IndexClient = orig

def test_tool_iserror_raises(tmp_path):
    # stub trả isError khi repo_path endswith "fail"
    class C: pass
    import mph.re.index as I
    c = IndexClient(CMD)
    try:
        import pytest as _p
        from mph.errors import HarnessError as HE
        with _p.raises(HE):
            c._tool("index_repository", {"repo_path": "x/fail"})
    finally:
        c.close()

def test_close_kills_on_timeout():
    import mph.re.index as I
    class FakeProc:
        class _Pipe:
            def close(self): pass
        stdin = _Pipe(); stdout = _Pipe()
        def wait(self, timeout=None):
            import subprocess as sp
            raise sp.TimeoutExpired(cmd="x", timeout=timeout)
        def kill(self):
            FakeProc.killed = True
        def returncode(self): return 0
    fp = FakeProc()
    I._shutdown(fp)
    assert FakeProc.killed is True

def test_non_json_tool_text_raises(tmp_path):
    import mph.re.index as I
    r = {"content": [{"type": "text", "text": "Error: boom"}], "isError": True}
    import pytest as _p
    from mph.errors import HarnessError as HE
    with _p.raises(HE):
        I._check_result(r)
