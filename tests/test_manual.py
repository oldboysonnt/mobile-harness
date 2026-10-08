# tests/test_manual.py — setup_manual: 1-click môi trường pentest thủ công.
# Yêu cầu user 2026-10-09: fail-soft (bước lỗi hiện lỗi rồi CHẠY TIẾP), vào bằng .ps1.
from pathlib import Path

from mph.manual import cheat_sheet, setup_manual


class FakeCfg:
    def __init__(self, tmp_path):
        self.sdk = tmp_path / "sdk"
        self.avd_name = "mph_avd"
        self.workspace = tmp_path / "ws"
        self.proxy_port = 8082
        self.burp_mcp_port = 9876
        self.tools_dir = tmp_path / "tools"
        self.frida_alias = "sysmondd"
        self.frida_port = 27042
        self.jadx_bin = "jadx.bat"


class _FakeAdb:
    def __init__(self, serial):
        self.serial = serial

    def run(self, *a, **k):
        class R:
            out = ""
        return R()


def _base_deps():
    """Deps all-green + ghi lại các call quan trọng."""
    calls = []
    pkgs = ["com.a"]

    class D:
        avd_serial = staticmethod(lambda name=None: "emulator-5554")
        wait_serial = staticmethod(lambda timeout=120, avd_name=None:
                                   "emulator-5554")
        wait_booted = staticmethod(lambda serial, adb: True)
        avd_boot = staticmethod(lambda *a, **k: calls.append("avd_boot"))
        adb_factory = staticmethod(lambda serial: _FakeAdb(serial))
        vendor_all = staticmethod(lambda cfg: {"rootavd": "r.zip",
                                               "frida-server": "f.xz"})
        brutdroid_vendor = staticmethod(
            lambda d: calls.append("brutdroid") or Path(str(d)))
        magisk_present = staticmethod(lambda adb: True)
        integrity_status = staticmethod(lambda adb, cfg: {"shamiko": True,
                                                          "pif": True})
        integrity_install = staticmethod(
            lambda adb, cfg, paths: calls.append("integ_install"))
        reboot_and_wait = staticmethod(
            lambda serial, adb: calls.append("reboot") or True)
        burp_start = staticmethod(lambda *a: 123)
        fetch_der = staticmethod(lambda port: b"DER")
        install_system_ca = staticmethod(lambda der, adb: "a1b2c3d4.0")
        proxy_on = staticmethod(lambda adb, port: calls.append("proxy_on"))
        frida_start = staticmethod(lambda adb, xz, alias=None, port=None:
                                   "/remote/sysmondd")
        frida_health = staticmethod(lambda adb: True)
        ensure_scripts = staticmethod(lambda: {"unpin": Path("unpin.js")})

        @staticmethod
        def _install(adb, apk):
            calls.append(("install", str(apk)))
            pkgs.append("com.foo")
            return True

        install_apk = staticmethod(_install)
        list_packages = staticmethod(lambda adb: list(pkgs))
        pull_apk = staticmethod(
            lambda adb, pkg, dest: calls.append(("pull", pkg)) or Path(str(dest)) / f"{pkg}.apk")
        decompile = staticmethod(
            lambda apk, out, jadx_bin: calls.append(("jadx", str(out))) or out)
        parse_manifest = staticmethod(lambda jadx_out: {"package": "com.foo"})
        write_summary = staticmethod(lambda m, dest: str(dest))
        ensure_indexed = staticmethod(lambda cfg, out: {"status": "ok"})
        root_flow = staticmethod(
            lambda cfg, paths, serial: calls.append("root_flow") or "emulator-5554")
        mcp_smoke = staticmethod(lambda: "10 tools")

    return D, calls


def test_green_no_apk(tmp_path):
    D, calls = _base_deps()
    ok, rows = setup_manual(FakeCfg(tmp_path), deps=D())
    assert ok is True
    assert [r[0] for r in rows] == [
        "vendor", "device", "adb-root", "root", "integrity",
        "burp", "ca", "proxy", "frida", "unpin-scripts", "mcp",
    ]
    assert all(r[1] for r in rows)
    assert "root_flow" not in calls  # đã root → không patch lại
    assert "integ_install" not in calls  # shamiko+pif đã có → skip
    root_row = next(r for r in rows if r[0] == "root")
    assert "Magisk" in root_row[2]


def test_fail_soft_burp_dead_ca_skipped_others_continue(tmp_path):
    D, calls = _base_deps()

    class DBad(D):
        @staticmethod
        def burp_start(*a):
            raise RuntimeError("burp chet")
    ok, rows = setup_manual(FakeCfg(tmp_path), deps=DBad())
    assert ok is False
    names = {r[0]: r for r in rows}
    assert names["burp"][1] is False and "burp chet" in names["burp"][2]
    assert names["ca"][1] is False and "skipped" in names["ca"][2]
    assert "proxy_on" in calls  # vẫn chạy tiếp
    assert names["proxy"][1] is True
    assert names["frida"][1] is True


def test_no_device_skips_device_steps_burp_still_runs(tmp_path):
    D, calls = _base_deps()

    class DNoDev(D):
        avd_serial = staticmethod(lambda name=None: None)
        wait_serial = staticmethod(lambda timeout=120, avd_name=None: None)
    ok, rows = setup_manual(FakeCfg(tmp_path), deps=DNoDev())
    assert ok is False
    names = {r[0]: r for r in rows}
    assert names["device"][1] is False
    for n in ("adb-root", "root", "integrity", "ca", "proxy", "frida"):
        assert names[n][1] is False and "skipped" in names[n][2], n
    assert names["burp"][1] is True      # host-side vẫn chạy
    assert names["unpin-scripts"][1] is True
    assert names["mcp"][1] is True       # MCP smoke vẫn chạy


def test_root_flow_runs_when_emulator_unrooted(tmp_path):
    D, calls = _base_deps()
    seen = []

    class DUnrooted(D):
        @staticmethod
        def magisk_present(adb):
            seen.append(1)
            return len(seen) > 1  # False trước root_flow, True sau

        @staticmethod
        def root_flow(cfg, paths, serial):
            calls.append(("root_flow", serial))
            return "emulator-9999"
    ok, rows = setup_manual(FakeCfg(tmp_path), deps=DUnrooted())
    assert ok is True
    assert ("root_flow", "emulator-5554") in calls
    root_row = next(r for r in rows if r[0] == "root")
    assert "emulator-9999" in root_row[2]


def test_physical_unrooted_red_no_root_flow(tmp_path):
    D, calls = _base_deps()

    class DPhys(D):
        avd_serial = staticmethod(lambda name=None: None)
        wait_serial = staticmethod(lambda timeout=120, avd_name=None: None)
        magisk_present = staticmethod(lambda adb: False)
    ok, rows = setup_manual(FakeCfg(tmp_path), deps=DPhys(), serial="redmi123")
    assert ok is False
    names = {r[0]: r for r in rows}
    assert names["device"][2] == "redmi123"
    assert names["adb-root"][1] is True and "skipped" in names["adb-root"][2]
    assert names["root"][1] is False and "root" in names["root"][2].lower()
    assert "root_flow" not in calls
    # integrity/ca cần root → skip; proxy vẫn chạy
    assert names["proxy"][1] is True


def test_integrity_missing_modules_installs_and_reboots(tmp_path):
    D, calls = _base_deps()

    class DNoPif(D):
        integrity_status = staticmethod(lambda adb, cfg: {"shamiko": True,
                                                          "pif": False})
    ok, rows = setup_manual(FakeCfg(tmp_path), deps=DNoPif())
    assert ok is True
    assert "integ_install" in calls and "reboot" in calls
    row = next(r for r in rows if r[0] == "integrity")
    assert "installed" in row[2]


def test_apk_flow_green(tmp_path):
    D, calls = _base_deps()
    apk = tmp_path / "target.apk"
    apk.write_bytes(b"PK")
    cfg = FakeCfg(tmp_path)
    ok, rows = setup_manual(cfg, apk=apk, deps=D())
    assert ok is True
    names = {r[0]: r for r in rows}
    assert names["apk-install"][1] is True
    assert names["apk-package"][2] == "com.foo"
    assert names["pull"][1] is True and names["jadx"][1] is True
    assert names["manifest"][1] is True and names["index"][1] is True
    assert ("pull", "com.foo") in calls
    ws = Path(cfg.workspace) / "com_foo"
    assert ws.is_dir()


def test_apk_explicit_package_skips_diff(tmp_path):
    D, calls = _base_deps()
    apk = tmp_path / "target.apk"
    apk.write_bytes(b"PK")

    class DNoNew(D):
        @staticmethod
        def _install(adb, a):
            return True  # không thêm package mới
    DNoNew.install_apk = staticmethod(DNoNew._install)
    ok, rows = setup_manual(FakeCfg(tmp_path), apk=apk, package="com.x",
                            deps=DNoNew())
    assert ok is True
    names = {r[0]: r for r in rows}
    assert names["apk-package"][2] == "com.x"


def test_apk_ambiguous_package_red_and_skips_re(tmp_path):
    D, calls = _base_deps()
    apk = tmp_path / "target.apk"
    apk.write_bytes(b"PK")

    class DNoNew(D):
        @staticmethod
        def _install(adb, a):
            return True
    DNoNew.install_apk = staticmethod(DNoNew._install)
    ok, rows = setup_manual(FakeCfg(tmp_path), apk=apk, deps=DNoNew())
    assert ok is False
    names = {r[0]: r for r in rows}
    assert names["apk-package"][1] is False and "--package" in names["apk-package"][2]
    for n in ("pull", "jadx", "manifest", "index"):
        assert names[n][1] is False and "skipped" in names[n][2], n


def test_cheat_sheet_mentions_tools(tmp_path):
    lines = cheat_sheet(FakeCfg(tmp_path), package="com.foo")
    text = "\n".join(lines)
    assert "8082" in text
    assert "mph frida unpin com.foo" in text
    assert "selftest" in text
    assert "mph screen" in text
    assert "MCP" in text  # các đầu giao tiếp cho AI agent


def test_mcp_failure_is_red_but_continues(tmp_path):
    D, calls = _base_deps()

    class DBadMcp(D):
        @staticmethod
        def mcp_smoke():
            raise RuntimeError("stdio server chet")
    ok, rows = setup_manual(FakeCfg(tmp_path), deps=DBadMcp())
    assert ok is False
    names = {r[0]: r for r in rows}
    assert names["mcp"][1] is False and "stdio server chet" in names["mcp"][2]
    assert names["proxy"][1] is True
    assert names["frida"][1] is True
