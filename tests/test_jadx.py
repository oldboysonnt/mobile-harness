# tests/test_jadx.py
from pathlib import Path

import pytest

from mph.errors import HarnessError
from mph.re.jadx import decompile

def _mk_out(tmp, with_sources=False):
    out = tmp / "jadx-out"
    (out / "sources").mkdir(parents=True, exist_ok=True)
    if with_sources:
        (out / "sources" / "X.java").write_text("class X{}")
    return out

def test_jadx_idempotent_skip(tmp_path):
    out = _mk_out(tmp_path, with_sources=True)
    calls = []
    decompile(tmp_path / "a.apk", out, runner=lambda c, timeout=None:
              calls.append(c) or type("R", (), {"returncode": 0})())
    assert calls == []  # đã có sources → skip

def test_jadx_nonzero_but_sources_ok(tmp_path):
    out = _mk_out(tmp_path, with_sources=True)
    (out / "sources" / "X.java").unlink()
    def runner(c, timeout=None):
        (out / "sources" / "X.java").write_text("class X{}")  # jadx vẫn sinh
        return type("R", (), {"returncode": 1})()
    got = decompile(tmp_path / "a.apk", out, runner=runner)
    assert got == out

def test_jadx_hard_fail_raises(tmp_path):
    out = tmp_path / "jadx-out"
    out.mkdir()
    with pytest.raises(HarnessError):
        decompile(tmp_path / "a.apk", out, runner=lambda c, timeout=None:
                  type("R", (), {"returncode": 1})())
