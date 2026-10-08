"""1-click setup môi trường pentest THỦ CÔNG (không AI — audit AI là việc sau cùng).

Ruling user 2026-10-09:
- vào bằng file ps1 (`setup-manual.ps1`), mọi logic nằm ở đây để test được;
- FAIL-SOFT: bước nào lỗi thì hiện lỗi rồi CHẠY TIẾP bước sau (không dừng chuỗi);
- các đầu giao tiếp cho AI agent (MCP stdio, Burp MCP, code graph) phải sẵn sàng.
"""
import json
import time
from dataclasses import dataclass
from pathlib import Path

from .device import avd as avd_mod
from .device.adb import Adb
from .errors import HarnessError
from .frida import scripts as frida_scripts
from .frida.server import _wait_frida_ps, frida_start as _frida_server_start
from .proxy import burp as burp_mod
from .proxy import cert as cert_mod
from .proxy import route as route_mod
from .re import apks as apks_mod, manifest as manifest_mod
from .re.index import ensure_indexed as _index_ensure
from .re.jadx import decompile as _jadx_decompile
from .root.brutdroid import brutdroid_vendor as _brutdroid_vendor
from .root.integrity import integrity_install as _integrity_install
from .root.integrity import integrity_status as _integrity_status
from .root.rootavd import magisk_present as _magisk_present
from .root.rootavd import root_via_rootavd as _root_via_rootavd
from .vendor import vendor_all as _vendor_all


def _wait_device_gone(serial: str, timeout: float = 90,
                      devices=Adb.devices, sleeper=time.sleep) -> bool:
    """Đợi serial biến mất khỏi `adb devices` (sau emu kill)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if serial not in {s for s, _ in devices()}:
            return True
        sleeper(3)
    return False


def _mcp_smoke() -> str:
    """Bắt tay MCP stdio server thật: initialize + tools/list trong 1 process."""
    import subprocess
    import sys

    root = Path(__file__).resolve().parent.parent
    if not (root / ".mcp.json").exists():
        raise HarnessError("khong thay .mcp.json tai repo root",
                           hint="file khai bao MCP stdio cho AI agent")
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_server"], cwd=str(root),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
    )
    try:
        reqs = "\n".join([
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05",
                                   "capabilities": {},
                                   "clientInfo": {"name": "mph-smoke",
                                                  "version": "1"}}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        ]) + "\n"
        proc.stdin.write(reqs)
        proc.stdin.flush()
        got: dict = {}
        for _ in range(8):
            line = proc.stdout.readline()
            if not line:
                break
            msg = json.loads(line)
            if msg.get("id") in (1, 2):
                got[msg["id"]] = msg
            if 1 in got and 2 in got:
                break
        for i in (1, 2):
            if i not in got or "error" in got.get(i, {}):
                raise HarnessError(f"mcp stdio handshake that bai (id={i})")
        tools = got[2].get("result", {}).get("tools", [])
        return f"{len(tools)} tools (stdio ok)"
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass
        proc.wait(timeout=10)


@dataclass(frozen=True)
class Deps:
    avd_serial = staticmethod(avd_mod.avd_serial)
    wait_serial = staticmethod(avd_mod.wait_serial)
    wait_booted = staticmethod(avd_mod.wait_booted)
    avd_boot = staticmethod(avd_mod.avd_boot)
    adb_factory = staticmethod(lambda serial: Adb(serial=serial))
    vendor_all = staticmethod(_vendor_all)
    brutdroid_vendor = staticmethod(_brutdroid_vendor)
    magisk_present = staticmethod(_magisk_present)
    integrity_status = staticmethod(_integrity_status)
    integrity_install = staticmethod(_integrity_install)
    burp_start = staticmethod(burp_mod.burp_start)
    fetch_der = staticmethod(cert_mod.fetch_der)
    install_system_ca = staticmethod(cert_mod.install_system_ca)
    proxy_on = staticmethod(route_mod.proxy_on)
    ensure_scripts = staticmethod(frida_scripts.ensure_scripts)
    list_packages = staticmethod(apks_mod.list_packages)
    install_apk = staticmethod(apks_mod.install_apk)
    pull_apk = staticmethod(apks_mod.pull_apk)
    decompile = staticmethod(_jadx_decompile)
    parse_manifest = staticmethod(manifest_mod.parse_manifest)
    write_summary = staticmethod(manifest_mod.write_summary)
    ensure_indexed = staticmethod(lambda cfg, out: _index_ensure(cfg, out))

    @staticmethod
    def _frida_start_default(adb, xz, alias=None, port=None):
        return _frida_server_start(adb, Path(str(xz)), alias=alias, port=port)

    frida_start = staticmethod(_frida_start_default)
    frida_health = staticmethod(
        lambda adb: _wait_frida_ps(adb, tries=3, delay=1.0))

    @staticmethod
    def _root_flow_default(cfg, paths, serial):
        """Emulator chưa root: kill AVD → patch ramdisk → boot lại → adb root."""
        Adb(serial=serial).run("emu", "kill")
        _wait_device_gone(serial)
        if "rootavd" not in paths:
            raise HarnessError("thieu artifact rootavd",
                               hint="bước vendor FAIL — chạy lại script")
        _root_via_rootavd(cfg, Path(paths["rootavd"]))
        avd_mod.avd_boot(Path(cfg.sdk), cfg.avd_name,
                         log_path=Path(cfg.workspace) / "logs" / "emulator.log")
        new = avd_mod.wait_serial(timeout=180, avd_name=cfg.avd_name)
        if not new or not avd_mod.wait_booted(new, Adb(serial=new)):
            raise HarnessError("boot lai sau root that bai",
                               hint="xem workspace/logs/emulator.log")
        Adb(serial=new).run("root")
        return new

    root_flow = staticmethod(_root_flow_default)

    @staticmethod
    def _reboot_default(serial, adb):
        adb.run("reboot")
        return avd_mod.wait_booted(serial, adb, timeout=420)

    reboot_and_wait = staticmethod(_reboot_default)
    mcp_smoke = staticmethod(_mcp_smoke)


def setup_manual(cfg, apk=None, package=None, serial=None,
                 deps: "Deps | None" = None,
                 on_row=None) -> tuple[bool, list[tuple[str, bool, str]]]:
    """Chuẩn bị MỌI công cụ pentest thủ công; fail-soft — lỗi một bước
    không chặn bước sau. Trả (ok tổng, rows)."""
    d = deps or Deps()
    rows: list[tuple[str, bool, str]] = []
    failed: set[str] = set()
    state: dict = {"serial": serial, "adb": None, "new_pkgs": set(),
                   "package": package, "ws": None, "apk": None}
    paths: dict = {}

    def step(name, fn, prereq=()):
        for p in prereq:
            if p in failed:
                rows.append((name, False, f"skipped: buoc '{p}' FAIL"))
                failed.add(name)
                if on_row:
                    on_row(rows[-1])
                return False
        try:
            detail = fn()
        except Exception as e:  # noqa: BLE001 — fail-soft: hiện lỗi, chạy tiếp
            rows.append((name, False, str(e)[:300]))
            failed.add(name)
            if on_row:
                on_row(rows[-1])
            return False
        if isinstance(detail, tuple):
            ok, text = detail[0], str(detail[1])[:300]
        else:
            ok = detail is not False
            text = "ok" if detail is None or detail is True else str(detail)[:300]
        rows.append((name, ok, text))
        if not ok:
            failed.add(name)
        if on_row:
            on_row(rows[-1])
        return ok

    # 1. vendor — tải artifact còn thiếu (magisk/shamiko/pif/frida/spic/rootavd)
    def _vendor():
        paths.update(d.vendor_all(cfg))
        d.brutdroid_vendor(Path(cfg.tools_dir) / "vendor" / "BrutDroid")
        return ",".join(sorted(paths))

    step("vendor", _vendor)

    # 2. device — AVD hoặc --serial thiết bị vật lý
    def _device():
        s = state["serial"] or d.avd_serial(cfg.avd_name)
        if not s:
            d.avd_boot(Path(cfg.sdk), cfg.avd_name,
                       log_path=Path(cfg.workspace) / "logs" / "emulator.log")
            s = d.wait_serial(timeout=180, avd_name=cfg.avd_name)
        if not s:
            return (False, "khong thay device — chay: mph setup run")
        if not d.wait_booted(s, d.adb_factory(s)):
            return (False, f"{s} khong boot xong trong timeout")
        state["serial"] = s
        state["adb"] = d.adb_factory(s)
        return s

    step("device", _device)

    # 3. adb-root — chỉ emulator; máy vật lý dùng su của Magisk
    def _adb_root():
        if not state["serial"].startswith("emulator-"):
            return (True, "skipped (vat ly — dung su)")
        return (state["adb"].run("root").out.strip() or "ok")[:120]

    step("adb-root", _adb_root, prereq=("device",))

    # 4. root — Magisk; emulator chưa root thì patch ramdisk + boot lại
    def _root():
        if d.magisk_present(state["adb"]):
            return "da co Magisk"
        if not state["serial"].startswith("emulator-"):
            return (False, "thiet bi vat ly chua root — cai Magisk thu cong "
                           "roi chay lai script")
        new = d.root_flow(cfg, paths, state["serial"])
        state["serial"] = new
        state["adb"] = d.adb_factory(new)
        if not d.magisk_present(state["adb"]):
            return (False, "root xong nhung khong thay magisk (su -v)")
        return f"rooted lai: {new}"

    step("root", _root, prereq=("device",))

    # 5. integrity — cài shamiko/pif nếu thiếu, reboot 1 lần để nạp module
    def _integrity():
        st = d.integrity_status(state["adb"], cfg)
        if st.get("shamiko") and st.get("pif"):
            return "skipped (shamiko+pif da co)"
        d.integrity_install(state["adb"], cfg, paths)
        if not d.reboot_and_wait(state["serial"], state["adb"]):
            return (False, "installed nhung reboot chua xong — reboot thu cong "
                           "de nap module zygisk")
        st2 = d.integrity_status(state["adb"], cfg)
        return f"installed + reboot: {json.dumps(st2, default=str)[:200]}"

    step("integrity", _integrity, prereq=("root",))

    # 6. burp — host-side, không phụ thuộc device
    ws = Path(cfg.workspace)
    step("burp", lambda: d.burp_start(
        cfg, ws / "_shared" / "burp" / "main.burp",
        ws / "_shared" / "burp" / "main.json"))

    # 7. CA vào system store (cần burp để fetch DER + root để bind-mount)
    def _ca():
        der = d.fetch_der(cfg.proxy_port)
        return d.install_system_ca(der, state["adb"])

    step("ca", _ca, prereq=("burp", "device", "root"))

    # 8. route traffic device → burp
    step("proxy", lambda: d.proxy_on(state["adb"], cfg.proxy_port),
         prereq=("device",))

    # 9. frida server ẩn + health
    def _frida():
        if "frida-server" not in paths:
            raise HarnessError("thieu frida-server (vendor FAIL)")
        remote = d.frida_start(state["adb"], paths["frida-server"],
                               alias=cfg.frida_alias, port=cfg.frida_port)
        healthy = d.frida_health(state["adb"])
        return (healthy, f"{remote} health={'ok' if healthy else 'fail'}")

    step("frida", _frida, prereq=("device", "vendor", "root"))

    # 10. scripts frida (unpin.js) sẵn sàng host-side
    step("unpin-scripts", lambda: ",".join(sorted(d.ensure_scripts())))

    # 11. MCP stdio smoke — đầu giao tiếp cho AI agent (dùng sau cùng)
    step("mcp", lambda: d.mcp_smoke())

    # 12. APK đích (tuỳ chọn): install → nhận diện package → pull/jadx/index
    if apk:
        def _apk_install():
            before = set(d.list_packages(state["adb"]))
            d.install_apk(state["adb"], Path(apk))
            state["new_pkgs"] = set(d.list_packages(state["adb"])) - before
            return f"installed ({len(state['new_pkgs'])} package moi)"

        step("apk-install", _apk_install, prereq=("device",))

        def _pkg():
            if state["package"]:
                return state["package"]
            new = state["new_pkgs"]
            if len(new) == 1:
                state["package"] = next(iter(new))
                return state["package"]
            return (False, f"khong xac dinh duoc package ({len(new)} moi) — "
                           "dung --package <ten>")

        step("apk-package", _pkg, prereq=("apk-install",))

        def _pull():
            pkg = state["package"]
            state["ws"] = apks_mod.app_workspace(cfg, pkg.replace(".", "_"))
            state["apk"] = d.pull_apk(state["adb"], pkg, state["ws"] / "apk")
            return str(state["apk"])

        step("pull", _pull, prereq=("apk-install", "apk-package"))

        step("jadx", lambda: str(d.decompile(
            state["apk"], state["ws"] / "jadx-out", cfg.jadx_bin)),
            prereq=("pull",))

        def _manifest():
            m = d.parse_manifest(state["ws"] / "jadx-out")
            d.write_summary(m, state["ws"] / "manifest.json")
            return m.get("package") or "ok"

        step("manifest", _manifest, prereq=("jadx",))
        step("index", lambda: json.dumps(
            d.ensure_indexed(cfg, state["ws"] / "jadx-out"))[:200],
            prereq=("jadx",))

    return all(ok for _, ok, _ in rows), rows


def cheat_sheet(cfg, package: str | None = None) -> list[str]:
    """Các lệnh/đầu giao tiếp sẵn sàng sau setup — in ra console + ghi file."""
    pkg = package or "<package>"
    bar = "=" * 64
    return [
        "",
        bar,
        " MOI TRUONG PENTEST THU CONG SAN SANG",
        bar,
        f" Burp proxy      : 127.0.0.1:{cfg.proxy_port} (CA da vao system store)",
        f" Frida unpin     : mph frida unpin {pkg}",
        " Frida server    : mph frida start | stop",
        " Man hinh        : mph screen screenshot | tap X Y | ui | type 'text'",
        " Danh sach app   : mph apks list",
        f" RE              : mph apks pull {pkg} ; mph re jadx|manifest|index <app>",
        " Play Integrity  : mph integrity check",
        " Kiem tra tong   : mph selftest --phase p4",
        " Tat proxy       : mph proxy off",
        " ---- dau giao tiep cho AI agent (san sang — dung sau cung) ----",
        " MCP stdio       : .mcp.json — mph_screenshot/tap/ui_find/packages/...",
        f" Burp MCP        : http://127.0.0.1:{cfg.burp_mcp_port} (SSE JSON-RPC)",
        " Code graph      : codebase-memory-mcp — index tai workspace/<app>/jadx-out",
        bar,
    ]
