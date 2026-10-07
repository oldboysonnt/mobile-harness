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
    assert cfg.frida_engine == "stock"
    assert cfg.tools_dir.name == "tools"
    assert cfg.fingerprints_dir.name == "fingerprints"
    assert cfg.magisk_slug == "topjohnwu/Magisk"
    assert cfg.shamiko_slug == "LSPosed/LSPosed.github.io"
    assert cfg.pif_slugs[0] == "osm0sis/PlayIntegrityFork"
    assert "frida/frida/releases" in cfg.frida_server_url_tpl
    assert cfg.spic_slug == "herzhenr/spic-android"
    assert "newbit/rootAVD" in cfg.rootavd_url

def test_re_section(tmp_path, monkeypatch):
    monkeypatch.delenv("ANDROID_HOME", raising=False)
    monkeypatch.delenv("BURP_PATH", raising=False)
    cfg = load_config(tmp_path / "nonexistent.toml")
    assert cfg.jadx_bin == "jadx"
    assert cfg.index_cmd.endswith("codebase-memory-mcp.exe")
    assert cfg.index_mode == "moderate"
