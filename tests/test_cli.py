# tests/test_cli.py
from typer.testing import CliRunner

import mph.cli as cli_mod
from mph.cli import app

runner = CliRunner()

def test_help_lists_groups():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0 and "setup" in r.output and "burp" in r.output

def test_burp_status_no_burp(tmp_path, monkeypatch):
    # dùng port ephemeral trống — 8080 trên máy dev bị Docker/WSL chiếm
    s = __import__("socket").socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    class FakeCfg:
        burp_exe = tmp_path / "nope.exe"
        burp_bin = tmp_path
        proxy_port = port
        burp_mcp_port = 9876

    monkeypatch.setattr(cli_mod, "_load_config", lambda: FakeCfg())
    r = runner.invoke(app, ["burp", "status"])
    assert r.exit_code == 0 and "not running" in r.output

def test_help_lists_new_groups():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    for word in ("frida", "root", "integrity", "bootstrap"):
        assert word in r.output

def test_help_lists_re_groups():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    for word in ("apks", "re"):
        assert word in r.output

def test_help_lists_p4_groups():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    for word in ("screen", "integrity"):
        assert word in r.output
