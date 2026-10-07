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
