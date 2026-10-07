# tests/test_frida_scripts.py
from pathlib import Path

from mph.frida.scripts import run_unpin, unpin_cmd

def test_unpin_cmd_shape():
    cmd = unpin_cmd("com.victim.app", Path("scripts/frida/unpin.js"))
    assert cmd[:2] == ["frida", "-U"]
    assert "-f" in cmd and "com.victim.app" in cmd
    assert str(Path("scripts/frida/unpin.js")) in cmd

def test_run_unpin_invokes_runner():
    calls = []

    def runner(cmd, timeout=None):
        calls.append(cmd)
        return (0, "ok")

    code, out = run_unpin("com.x", Path("s.js"), runner=runner)
    assert (code, out) == (0, "ok") and calls[0][0] == "frida"
