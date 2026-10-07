# tests/test_cli.py
from typer.testing import CliRunner

import mph.cli as cli_mod
from mph.cli import app

runner = CliRunner()

def test_help_lists_groups():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0 and "setup" in r.output and "burp" in r.output

def test_burp_status_no_burp(tmp_path, monkeypatch):
    class FakeCfg:
        burp_exe = tmp_path / "nope.exe"
        burp_bin = tmp_path
        proxy_port = 8080
        burp_mcp_port = 9876

    monkeypatch.setattr(cli_mod, "_load_config", lambda: FakeCfg())
    r = runner.invoke(app, ["burp", "status"])
    assert r.exit_code == 0 and "not running" in r.output
