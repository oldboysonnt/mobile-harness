# tests/test_burp.py
import socket
from mph.proxy.burp import listener_config, wait_port, burp_start, build_cmd

def test_listener_config_shape():
    c = listener_config(8080)
    lst = c["project_options"]["proxy"]["request_listeners"][0]
    assert lst == {"listen_mode": "all_interfaces", "listener_port": 8080, "running": True}

def test_wait_port_timeout():
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    assert wait_port(port, timeout=0.3, poller=lambda p: False) is False

def test_wait_port_open():
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
    port = srv.getsockname()[1]
    try:
        assert wait_port(port, timeout=2) is True
    finally:
        srv.close()

def test_start_idempotent_when_port_open(tmp_path):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    srv.listen(1)

    class FakeCfg:
        burp_exe = tmp_path / "burpsuite_pro.jar"
        burp_bin = tmp_path
        proxy_port = port
    try:
        assert burp_start(FakeCfg(), tmp_path / "p.burp", tmp_path / "c.json",
                          popen=None) == -1
    finally:
        srv.close()

def test_build_cmd_java_launcher(tmp_path):
    class FakeCfg:
        burp_exe = tmp_path / "BurpSuitePro" / "burpsuite_pro.jar"
        burp_bin = tmp_path
        proxy_port = 8080
    cmd, cwd = build_cmd(FakeCfg(), tmp_path / "p.burp", tmp_path / "c.json")
    assert cmd[0] == "java"
    assert any(a.startswith("-javaagent:") and "BurpLoaderKeygen.jar" in a for a in cmd)
    assert cmd[cmd.index("-jar") + 1] == str(FakeCfg.burp_exe)
    i = cmd.index("--project-file")
    assert cmd[i + 1] == str(tmp_path / "p.burp")
    assert cwd == str(tmp_path)

def test_build_cmd_exe_launcher(tmp_path):
    class FakeCfg:
        burp_exe = tmp_path / "BurpSuitePro.exe"
        burp_bin = tmp_path
        proxy_port = 8080
    cmd, cwd = build_cmd(FakeCfg(), tmp_path / "p.burp", tmp_path / "c.json")
    assert cmd[0] == str(FakeCfg.burp_exe) and cwd is None
