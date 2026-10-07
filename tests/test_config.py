# tests/test_config.py
import pytest
from mph.config import load_config, Config
from mph.errors import HarnessError

def test_load_defaults(tmp_path, monkeypatch):
    monkeypatch.delenv("ANDROID_HOME", raising=False)
    monkeypatch.delenv("BURP_PATH", raising=False)
    cfg = load_config(tmp_path / "nonexistent.toml")  # file thiếu → dùng default
    assert cfg.proxy_port == 8080
    assert cfg.burp_mcp_port == 9876
    assert cfg.avd_name == "mph_avd"
    assert cfg.image == "system-images;android-34;google_apis;x86_64"
    assert cfg.sdk.name == "Sdk"

def test_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("ANDROID_HOME", str(tmp_path / "other_sdk"))
    cfg = load_config(tmp_path / "nonexistent.toml")
    assert cfg.sdk == tmp_path / "other_sdk"

def test_explicit_file(tmp_path):
    f = tmp_path / "mph.toml"
    f.write_text('[proxy]\nport = 9090\n', encoding="utf-8")
    cfg = load_config(f)
    assert cfg.proxy_port == 9090

def test_harness_error_hint():
    e = HarnessError("burp khong start", hint="kiem tra license")
    assert "kiem tra license" in str(e)

def test_no_burp_returns_none_not_raise(tmp_path, monkeypatch):
    monkeypatch.delenv("BURP_PATH", raising=False)
    import mph.config as C
    monkeypatch.setattr(C, "_BURP_CANDIDATES", ())
    cfg = C.load_config(tmp_path / "nonexistent.toml")
    assert cfg.burp_exe is None  # doctor phải in FAIL, không traceback

def test_root_and_frida_sections(tmp_path, monkeypatch):
    monkeypatch.delenv("ANDROID_HOME", raising=False)
    monkeypatch.delenv("BURP_PATH", raising=False)
    cfg = load_config(tmp_path / "nonexistent.toml")
    assert cfg.frida_alias == "sysmondd"
    assert cfg.tools_dir.name == "tools"
    assert cfg.fingerprints_dir.name == "fingerprints"
    assert "topjohnwu/Magisk" in cfg.magisk_url
    assert "LSPosed/LSPosed.github.io" in cfg.shamiko_url
    assert "chiteroman/PlayIntegrityFork" in cfg.pif_slugs
    assert "jyotidwi/PlayIntegrityFix" in cfg.pif_slugs
    assert "CrackerCat/strongR-frida-android" in cfg.strongr_url_tpl
    assert "herzhenr/spic-android" in cfg.spic_url
    assert "newbit/rootAVD" in cfg.rootavd_url
