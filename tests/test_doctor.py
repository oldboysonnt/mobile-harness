# tests/test_doctor.py
from mph.doctor import check_env, Probes

def make_cfg(tmp_path, **kw):
    from mph.config import Config
    d = dict(sdk=tmp_path/"Sdk", burp_exe=tmp_path/"burp.exe", burp_bin=tmp_path/"bin",
             git_bash=tmp_path/"bash.exe",
             avd_name="mph_avd", image="x", proxy_port=8080, burp_mcp_port=9876,
             workspace=tmp_path/"ws")
    d.update(kw)
    return Config(**d)

def test_all_ok(tmp_path):
    cfg = make_cfg(tmp_path)
    probes = Probes(exists=lambda p: True, which=lambda c: "C:/x/" + c,
                    devices=lambda: [("emulator-5554", "device")])
    rows = check_env(cfg, probes)
    assert all(ok for _, ok, _ in rows) and len(rows) >= 5

def test_missing_adb_flags_row(tmp_path):
    cfg = make_cfg(tmp_path)
    probes = Probes(exists=lambda p: True, which=lambda c: None, devices=lambda: [])
    rows = check_env(cfg, probes)
    adb_row = next(r for r in rows if r[0] == "adb")
    assert adb_row[1] is False
