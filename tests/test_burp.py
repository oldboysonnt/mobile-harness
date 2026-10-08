# tests/test_burp.py
import socket
import threading
from mph.proxy.burp import listener_config, wait_port, burp_start, build_cmd, _probe

def _serve_http(port_holder, respond=True):
    """Listener giả Burp: accept + trả dòng status HTTP (hoặc reset như docker)."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(4)
    port_holder.append(srv.getsockname()[1])

    def loop():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            with conn:
                try:
                    conn.recv(1024)
                    if respond:
                        conn.sendall(b"HTTP/1.0 200 OK\r\n\r\n")
                except OSError:
                    pass

    threading.Thread(target=loop, daemon=True).start()
    return srv

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
    holder = []
    srv = _serve_http(holder)
    try:
        assert wait_port(holder[0], timeout=3) is True
    finally:
        srv.close()

def test_probe_rejects_silent_tcp_lure():
    """Hồi quy 2026-10-09: docker backend [::]:8080 dual-stack chấp nhận TCP
    rồi reset GET — không được coi là Burp."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    def loop():
        try:
            conn, _ = srv.accept()
            conn.recv(1024)
            conn.close()  # không trả gì — giống reset của docker
        except OSError:
            pass

    threading.Thread(target=loop, daemon=True).start()
    try:
        assert _probe(port) is False
    finally:
        srv.close()

def test_probe_accepts_http_listener():
    holder = []
    srv = _serve_http(holder)
    try:
        assert _probe(holder[0]) is True
    finally:
        srv.close()

def test_start_idempotent_when_port_open(tmp_path):
    holder = []
    srv = _serve_http(holder)

    class FakeCfg:
        burp_exe = tmp_path / "burpsuite_pro.jar"
        burp_bin = tmp_path
        proxy_port = holder[0]
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
    # dạng --option=value: picocli qua shell mất value ở dạng space (fix 2026-10-09)
    assert f"--project-file={tmp_path / 'p.burp'}" in cmd
    assert f"--config-file={tmp_path / 'c.json'}" in cmd
    assert "--auto-repair" in cmd
    assert cwd == str(tmp_path)

def test_build_cmd_exe_launcher(tmp_path):
    class FakeCfg:
        burp_exe = tmp_path / "BurpSuitePro.exe"
        burp_bin = tmp_path
        proxy_port = 8080
    cmd, cwd = build_cmd(FakeCfg(), tmp_path / "p.burp", tmp_path / "c.json")
    assert cmd[0] == str(FakeCfg.burp_exe) and cwd is None

def test_vbs_cmd_shape(tmp_path):
    from mph.proxy.burp import build_vbs_cmd
    (tmp_path / "burp.vbs").write_text("'vbs", encoding="ascii")
    class FakeCfg:
        burp_bin = tmp_path
    cmd = build_vbs_cmd(FakeCfg())
    assert cmd[0].endswith("wscript.exe")
    assert any(str(tmp_path / "burp.vbs") in a for a in cmd)

def test_burp_start_jar_uses_build_cmd_skips_wizard(tmp_path, monkeypatch):
    """jar → java + --project-file= (bỏ wizard), không gọi wscript."""
    import mph.proxy.burp as b

    calls = []
    monkeypatch.setattr(b, "wait_port",
                        lambda port, timeout=0: True)  # port "mở" sau launch

    class _Popen:
        def __init__(self, cmd, cwd=None, **k):
            calls.append((cmd, cwd))
            self.pid = 4242

    (tmp_path / "BurpSuitePro").mkdir()
    (tmp_path / "BurpSuitePro" / "BurpLoaderKeygen.jar").write_bytes(b"K")
    jar = tmp_path / "BurpSuitePro" / "burpsuite_pro.jar"
    jar.write_bytes(b"J")

    class FakeCfg:
        burp_exe = jar
        burp_bin = tmp_path
        proxy_port = 59999  # port đóng → không idempotent-skip
    pid = burp_start(FakeCfg(), tmp_path / "p.burp", tmp_path / "c.json",
                     popen=_Popen)
    assert pid == 4242
    cmd, cwd = calls[0]
    assert cmd[0] == "java" and cwd == str(tmp_path)
    assert any(a.startswith("--project-file=") for a in cmd)
    assert not any("wscript" in a for a in cmd)
    assert (tmp_path / "c.json").exists()  # config vẫn được ghi

def test_burp_start_exe_falls_back_to_vbs(tmp_path, monkeypatch):
    """burp_exe không phải .jar → giữ vbs launcher cũ."""
    import mph.proxy.burp as b

    calls = []
    monkeypatch.setattr(b, "wait_port", lambda port, timeout=0: True)

    class _Popen:
        def __init__(self, cmd, cwd=None, **k):
            calls.append((cmd, cwd))
            self.pid = 77

    (tmp_path / "burp.vbs").write_text("'vbs", encoding="ascii")

    class FakeCfg:
        burp_exe = tmp_path / "BurpSuitePro.exe"
        burp_bin = tmp_path
        proxy_port = 59998
    assert burp_start(FakeCfg(), tmp_path / "p.burp",
                      tmp_path / "c.json", popen=_Popen) == 77
    cmd, cwd = calls[0]
    assert cmd[0].endswith("wscript.exe") and cwd == str(tmp_path)
