# tests/test_bootstrap.py
from pathlib import Path
from mph.bootstrap import ensure_cmdline_tools, CMDLINE_TOOLS_URL, install_image, create_avd

def test_cmdline_tools_idempotent(tmp_path):
    downloads = []
    def fake_fetch(url, dest):
        downloads.append(url)
        import zipfile
        with zipfile.ZipFile(dest, "w") as zf:      # giả lập cấu trúc zip thật
            zf.writestr("cmdline-tools/bin/sdkmanager.bat", "@echo off")
    def fake_unzip(zip_path: Path, dest: Path):
        import zipfile
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(dest)
    sdk, cache = tmp_path / "Sdk", tmp_path / "cache"
    r1 = ensure_cmdline_tools(sdk, cache, fetch=fake_fetch, unzip=fake_unzip)
    r2 = ensure_cmdline_tools(sdk, cache, fetch=fake_fetch, unzip=fake_unzip)
    assert r1 == r2 == sdk / "cmdline-tools" / "latest"
    assert len(downloads) == 1 and downloads[0] == CMDLINE_TOOLS_URL

def test_install_image_command(tmp_path):
    calls = []
    def runner(cmd, timeout=None, **kw):
        calls.append(cmd); return (0, "ok", "")
    install_image(tmp_path, "system-images;android-34;google_apis;x86_64", runner)
    joined = [" ".join(c) for c in calls]
    assert any("--licenses" in j for j in joined)
    assert any("android-34" in j for j in joined)

def test_create_avd_force(tmp_path):
    calls = []
    def runner(cmd, timeout=None, **kw):
        calls.append(cmd); return (0, "ok", "")
    create_avd(tmp_path, "mph_avd", "system-images;android-34;google_apis;x86_64", runner)
    create_avd(tmp_path, "mph_avd", "system-images;android-34;google_apis;x86_64", runner)
    assert calls[0][1:3] == ["create", "avd"] and "avdmanager.bat" in calls[0][0]
    assert all("--force" in c for c in calls) and len(calls) == 2
