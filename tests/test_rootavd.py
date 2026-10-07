# tests/test_rootavd.py
from pathlib import Path

from mph.root.rootavd import build_root_cmd, magisk_present, root_via_rootavd

def test_build_cmd_uses_git_bash():
    cmd = build_root_cmd(Path("C:/gb/bash.exe"), Path("t/rootavd"),
                         Path("avd/mph_avd.avd"))
    assert Path(cmd[0]).as_posix() == "C:/gb/bash.exe"  # Path chuẩn hoá backslash
    assert any("rootAVD.sh" in a for a in cmd)
    assert cmd[-1].endswith("mph_avd.avd")

def _fake_runner(out, code=0):
    def runner(cmd, env=None, timeout=None):
        runner.last_cmd, runner.last_env = cmd, env
        return code, out, ""
    return runner

def test_root_ok_on_all_done():
    r = _fake_runner("[*] All done!")
    assert root_via_rootavd(None, Path("t"), runner=r) is True

def test_root_ok_on_already():
    r = _fake_runner("already patched")
    assert root_via_rootavd(None, Path("t"), runner=r) is True

def test_root_fail_sets_env(tmp_path):
    class C:
        sdk = tmp_path
        git_bash = Path("bash")
        avd_name = "mph_avd"
    r = _fake_runner("some error", code=1)
    try:
        root_via_rootavd(C(), Path("t"), runner=r)
        raised = False
    except Exception:
        raised = True
    assert raised and r.last_env["ANDROID_HOME"] == str(tmp_path)

def test_magisk_present():
    class R:
        ok = True; out = "29.4:M"; err = ""; code = 0
    class A:
        def run(self, *a, **k):
            return R()
    assert magisk_present(A()) is True
