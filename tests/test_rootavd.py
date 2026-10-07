# tests/test_rootavd.py
from pathlib import Path

from mph.root.rootavd import build_root_cmd, magisk_present, root_via_rootavd

def _fake_cfg(tmp_path):
    class C:
        sdk = tmp_path / "Sdk"
        git_bash = Path("C:/Program Files/Git/bin/bash.exe")
        avd_name = "mph_avd"
        image = "system-images;android-34;google_apis;x86_64"
    img = C.sdk / "system-images" / "android-34" / "google_apis" / "x86_64"
    img.mkdir(parents=True)
    (img / "ramdisk.img").write_bytes(b"fake")
    return C()

def test_build_cmd_uses_git_bash_and_ramdisk(tmp_path):
    ramdisk = tmp_path / "img" / "ramdisk.img"
    cmd = build_root_cmd(Path("C:/gb/bash.exe"), Path("t/rootavd"), ramdisk)
    assert Path(cmd[0]).as_posix() == "C:/gb/bash.exe"
    assert any("rootAVD.sh" in a for a in cmd)
    assert cmd[-1].endswith("ramdisk.img") and "\\" not in cmd[-1]

def _fake_runner(out, code=0):
    def runner(cmd, env=None, timeout=None, cwd=None):
        runner.last_cmd, runner.last_env, runner.last_cwd = cmd, env, cwd
        return code, out, ""
    return runner

def test_root_ok_on_all_done(tmp_path):
    r = _fake_runner("[*] All done!")
    assert root_via_rootavd(_fake_cfg(tmp_path), Path("t"), runner=r) is True

def test_root_ok_on_already(tmp_path):
    r = _fake_runner("already patched")
    assert root_via_rootavd(_fake_cfg(tmp_path), Path("t"), runner=r) is True

def test_root_fail_sets_env_and_cwd(tmp_path):
    cfg = _fake_cfg(tmp_path)
    r = _fake_runner("some error", code=1)
    try:
        root_via_rootavd(cfg, Path("t/rootavd"), runner=r)
        raised = False
    except Exception:
        raised = True
    assert raised
    assert r.last_env["ANDROID_HOME"] == str(cfg.sdk)
    assert r.last_cwd == str(Path("t/rootavd"))

def test_magisk_present():
    class R:
        ok = True; out = "29.4:M"; err = ""; code = 0
    class A:
        def run(self, *a, **k):
            return R()
    assert magisk_present(A()) is True
