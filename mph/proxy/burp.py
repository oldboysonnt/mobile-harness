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
    with socket.socket() as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", port)) == 0


def build_cmd(cfg, project_file: Path, config_file: Path) -> tuple[list[str], str | None]:
    """Dựng lệnh launch Burp; trả (cmd, cwd|None)."""
    jar = Path(cfg.burp_exe)
    burp_args = [
        "--project-file", str(project_file),
        "--config-file", str(config_file),
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


def burp_start(cfg, project_file: Path, config_file: Path,
               popen=subprocess.Popen) -> int:
    """Start Burp; idempotent (port đã mở → -1). Trả pid."""
    if _probe(cfg.proxy_port):
        return -1
    if not Path(cfg.burp_exe).exists():
        raise HarnessError(
            f"burp exe khong ton tai: {cfg.burp_exe}",
            hint="dat BURP_PATH hoac sua mph.toml [paths]",
        )
    Path(project_file).parent.mkdir(parents=True, exist_ok=True)
    Path(config_file).write_text(
        json.dumps(listener_config(cfg.proxy_port)), encoding="utf-8"
    )
    cmd, cwd = build_cmd(cfg, Path(project_file), Path(config_file))
    proc = popen(cmd, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_port(cfg.proxy_port, timeout=90):
        raise HarnessError(
            "burp khong mo port sau 90s",
            hint="mo Burp thu cong lan dau de hoan tat wizard license, roi chay lai",
        )
    return proc.pid
