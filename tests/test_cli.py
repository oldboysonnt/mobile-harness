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

def test_setup_manual_streams_rows_and_exit_code(tmp_path, monkeypatch):
    class FakeCfg:
        workspace = tmp_path

    def _fake(cfg, apk, package, serial, on_row=None):
        if on_row:
            on_row(("vendor", True, "ok"))
        return True, [("vendor", True, "ok")]

    monkeypatch.setattr(cli_mod, "_load_config", lambda: FakeCfg())
    monkeypatch.setattr(cli_mod, "manual_setup", _fake)
    monkeypatch.setattr(cli_mod, "manual_cheat_sheet",
                        lambda cfg, package=None: ["SHEET-LINE"])
    r = runner.invoke(app, ["setup", "manual"])
    assert r.exit_code == 0
    assert "[OK ] vendor: ok" in r.output
    assert "SHEET-LINE" in r.output
    assert (tmp_path / "CHEATSHEET.md").read_text(encoding="utf-8") == "SHEET-LINE"

def test_setup_manual_fail_exit_1(tmp_path, monkeypatch):
    class FakeCfg:
        workspace = tmp_path

    def _fake(cfg, apk, package, serial, on_row=None):
        if on_row:
            on_row(("burp", False, "chet"))
        return False, [("burp", False, "chet")]

    monkeypatch.setattr(cli_mod, "_load_config", lambda: FakeCfg())
    monkeypatch.setattr(cli_mod, "manual_setup", _fake)
    monkeypatch.setattr(cli_mod, "manual_cheat_sheet",
                        lambda cfg, package=None: ["SHEET"])
    r = runner.invoke(app, ["setup", "manual", "--apk", "x.apk"])
    assert r.exit_code == 1
    assert "[FAIL] burp: chet" in r.output

def test_python_dash_m_entrypoint():
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-m", "mph", "--help"],
                       capture_output=True, text=True, timeout=60,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0 and "setup" in r.stdout
