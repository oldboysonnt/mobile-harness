"""Khởi động Burp Suite Pro với listener json, đợi port sẵn sàng.

Ruling (Task 1): máy này launch Burp qua
`java -noverify -javaagent:BurpLoaderKeygen.jar ... -jar burpsuite_pro.jar`
(đúng như burp.vbs) — build_cmd dựng lệnh đó khi burp_exe là .jar.
"""
import json
import socket
import subprocess
import time
from pathlib import Path

from ..errors import HarnessError

_ADD_OPENS = (
    "--add-opens=java.desktop/javax.swing=ALL-UNNAMED",
    "--add-opens=java.base/java.lang=ALL-UNNAMED",
    "--add-opens=java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED",
    "--add-opens=java.base/jdk.internal.org.objectweb.asm.tree=ALL-UNNAMED",
    "--add-opens=java.base/jdk.internal.org.objectweb.asm.Opcodes=ALL-UNNAMED",
)


def listener_config(port: int) -> dict:
    """Cấu hình listener cho `--config-file` (schema project_options)."""
    return {
        "project_options": {
            "proxy": {
                "request_listeners": [
                    {
                        "listen_mode": "all_interfaces",
                        "listener_port": port,
                        "running": True,
                    }
                ]
            }
        }
    }


def wait_port(port: int, timeout: float = 60, poller=None) -> bool:
    """Đợi port mở; trả False khi hết timeout."""
    check = poller or _probe
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check(port):
            return True
        time.sleep(1.0)
    return False


def _probe(port: int) -> bool:
    """HTTP-aware: com.docker.backend chiếm [::]:8080 dual-stack — TCP connect
    thành công nhưng GET bị reset. Chỉ coi là Burp khi có dòng status HTTP."""
    with socket.socket() as s:
        s.settimeout(2.0)
        if s.connect_ex(("127.0.0.1", port)) != 0:
            return False
        try:
            s.sendall(b"GET / HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n")
            data = s.recv(16)
        except OSError:
            return False
        return bool(data) and data.startswith(b"HTTP/")


def build_cmd(cfg, project_file: Path, config_file: Path) -> tuple[list[str], str | None]:
    """Dựng lệnh launch Burp; trả (cmd, cwd|None).

    Dạng `--option=value` (không phải `--option value`): qua shell trung gian
    (cmd/wscript) picocli của Burp 2026 mất value ở dạng space (thực nghiệm
    2026-10-09: "Expected a value for option project-file").
    """
    jar = Path(cfg.burp_exe)
    burp_args = [
        f"--project-file={project_file}",
        f"--config-file={config_file}",
        "--auto-repair",
    ]
    if jar.suffix == ".jar":
        bin_dir = Path(cfg.burp_bin)
        keygen = bin_dir / "BurpSuitePro" / "BurpLoaderKeygen.jar"
        cmd = (
            ["java", "-noverify", "-javaagent:" + str(keygen)]
            + list(_ADD_OPENS)
            + ["-jar", str(jar)]
            + burp_args
        )
        return cmd, str(bin_dir)
    return [str(jar)] + burp_args, None


def build_vbs_cmd(cfg) -> list[str]:
    """Launcher chuẩn của máy: wscript burp.vbs (license/settings đã nhớ)."""
    vbs = Path(cfg.burp_bin) / "burp.vbs"
    if not vbs.exists():
        raise HarnessError(f"khong thay {vbs}",
                            hint="sua mph.toml [paths] burp_bin")
    return ["wscript.exe", str(vbs)]


def burp_start(cfg, project_file: Path, config_file: Path,
               popen=subprocess.Popen) -> int:
    """Start Burp không cần click wizard (fix 2026-10-09).

    Thực nghiệm máy dev (Burp Pro 2026.1.1 + keygen):
    - burp.vbs / java không `--project-file` → wizard "chọn project" chờ
      click mãi, listener không bao giờ mở (exit-code 1 của chain).
    - java + `--project-file=` (dạng `=`) → bỏ wizard, vào thẳng project;
      Burp mở listener mặc định 127.0.0.1:8080 bất kể `--config-file`
      (request_listeners.running không áp qua config-file lẫn
      user-config-file — đã thử all_interfaces/loopback_only/project mới).
      → mph.toml đặt [proxy] port = 8080 (IPv4 trống; wslrelay chỉ IPv6 ::1).
    Idempotent (port đã mở → -1). Trả pid.
    """
    if _probe(cfg.proxy_port):
        return -1
    if cfg.burp_exe is None:
        raise HarnessError("khong tim thay Burp",
                            hint="dat BURP_PATH hoac sua mph.toml [paths]")
    Path(project_file).parent.mkdir(parents=True, exist_ok=True)
    Path(config_file).write_text(
        json.dumps(listener_config(cfg.proxy_port)), encoding="utf-8"
    )
    if Path(cfg.burp_exe).suffix == ".jar":
        cmd, cwd = build_cmd(cfg, Path(project_file), Path(config_file))
    else:
        cmd, cwd = build_vbs_cmd(cfg), str(Path(cfg.burp_bin))
    proc = popen(cmd, cwd=cwd,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_port(cfg.proxy_port, timeout=240):
        raise HarnessError(
            "burp khong mo port sau 240s",
            hint="mo Burp thu cong (burp.vbs), kiem tra listener "
                 f"127.0.0.1:{cfg.proxy_port} trong Proxy settings",
        )
    return proc.pid
