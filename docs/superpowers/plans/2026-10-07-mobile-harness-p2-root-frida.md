# Mobile Pentest Harness — P2 Root & Instrumentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nâng AVD từ "adb root" (P1) lên **Magisk đầy đủ + integrity stack L1–L3** và **frida ẩn (StrongR/hluda) + SSL unpin**, DoD = `mph selftest --phase p2` xanh thêm các hàng root/frida.

**Architecture:** Bổ sung `mph/root/` (RootAVD, Magisk, integrity) và `mph/frida/` (server + scripts) trên nền P1. Mọi artifact ngoài tải về `tools/` pin-version trong `mph.toml`; mọi lệnh device đi qua `Adb` có sẵn.

**Tech Stack:** Python 3.12 + Typer + pytest (có sẵn); ngoài: Magisk, rootAVD (Git Bash), Shamiko, PlayIntegrityFix, StrongR-frida (hluda), SPIC apk, unpin.js vendored.

**Spec:** `docs/superpowers/specs/2026-10-07-mobile-pentest-harness-design.md` (§4.3 stack 5 lớp, §4.1 device layer, §10 roadmap P2, §11 risks).

**Ruling giữ từ P1:** rootAVD là provider root mặc định (BrutDroid vendored ở Task 8 làm đường thay thế experimental). Verdict Play Integrity tự động (SPIC + đọc UI) cần screen layer của P4 — P2 chỉ có `mph integrity status` (module/zygisk/denylist/fingerprint); `mph integrity check` (verdict thật) dời sang P4, ghi rõ trong ledger.

**Ngoài phạm vi P2 này:** L3 TrickyStore + keybox (spec ghi "user tự cấp keybox" — làm khi có keybox, sau P2); L4 frida hook verdict phía app (thuộc Phase Audit P5 — cần recon chỉ đích danh hàm verify).

## Global Constraints

- Windows 11, Git Bash (`C:\Program Files\Git\bin\bash.exe` = `Config.git_bash`), SDK `%LOCALAPPDATA%\Android\Sdk` (env `ANDROID_HOME` override), proxy port **8082** trên máy dev (8080 bị Docker chiếm — ruling P1).
- Idempotent mọi lệnh; immutable config; lỗi `HarnessError(msg, hint)`; file < 400 dòng; conventional commits không attribution.
- Deps không thêm mới ngoài `pyproject` hiện có (typer, cryptography, pytest) — giải nén `.xz`/`.zip` bằng `tar` bsdtar có sẵn Windows 11, không thêm lib.
- Pin ngoài trong `mph.toml`: mọi URL/SHA phải đọc từ config, không hardcode trong code.
- AVD workhorse: `mph_avd` (API 34 google_apis x86_64) từ P1.

## Review Focus

1. **Tải về hỏng giữa chừng (zip nửa vời)** → lần chạy sau phải tự tải lại, không dùng artifact đỏng đảnh — Task 2 test `test_partial_download_refetched`.
2. **frida-serveralias trùng tên process hệ thống** → app scan process list phát hiện — Task 6 test alias chỉ chứa `[a-z0-9_]` và ≠ danh sách cấm (`frida`, `hluda`, `gum`).
3. **Magisk chưa mở (rootAVD chưa xong) mà lệnh chạy** → phải fail rõ "chay mph root install truoc", không traceback thô — Task 4 test `test_magisk_missing_fails_with_hint`.
4. **PIF fingerprint bị ban (404/asset đổi tên)** → resolver thử candidate kế tiếp rồi mới fail với đủ danh sách đã thử — Task 2 test `test_pif_resolver_fallback`.
5. **Lần 2 chạy setup root (Magisk đã cài)** → không cài lại/prompt, trả "already" — Task 3/4 test idempotent paths.

---

### Task 1: Config mở rộng cho root/frida/vendor

**Files:**
- Modify: `mph.toml`, `mph/config.py`
- Test: `tests/test_config.py` (thêm test)

**Interfaces:**
- Produces: `Config` thêm fields: `magisk_url: str`, `shamiko_url: str`, `pif_slugs: list[str]`, `strongr_url_tpl: str` (chứa `{ver}`), `frida_client_ver: str`, `spic_url: str`, `rootavd_url: str`, `frida_alias: str`, `fingerprints_dir: Path`, `tools_dir: Path`. Mặc định phải khớp mph.toml.

- [ ] **Step 1: Failing tests** — thêm vào `tests/test_config.py`:

```python
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
```

- [ ] **Step 2: Run** `python -m pytest tests/test_config.py -v` — expect FAIL (AttributeError).

- [ ] **Step 3: Implement** — thêm vào `mph.toml`:

```toml
[root]
magisk_url  = 'https://github.com/topjohnwu/Magisk/releases/latest/download/Magisk-v29.4.apk'
shamiko_url = 'https://github.com/LSPosed/LSPosed.github.io/releases/latest/download/Shamiko-v0.7.6-219.zip'
pif_slugs   = ["chiteroman/PlayIntegrityFork", "jyotidwi/PlayIntegrityFix", "osm0sis/PlayIntegrityFork"]

[frida]
client_ver  = "16.7.19"
strongr_url_tpl = 'https://github.com/CrackerCat/strongR-frida-android/releases/download/{ver}/hluda-server-{ver}-android-x86_64.xz'
alias       = "sysmondd"

[vendor]
spic_url    = 'https://github.com/herzhenr/spic-android/releases/latest/download/app-release.apk'
rootavd_url = 'https://gitlab.com/newbit/rootAVD/-/archive/master/rootAVD-master.tar.gz'
```

và `Config` thêm 9 fields tương ứng (đọc `[root]`, `[frida]`, `[vendor]` theo đúng pattern `[paths]` hiện có; `tools_dir=_REPO_ROOT/"tools"`, `fingerprints_dir=_REPO_ROOT/"fingerprints"`; `pif_slugs` là `list[str]`).

- [ ] **Step 4: Run** — PASS. **Step 5: Commit** `feat: config for root/frida vendor pins`.

---

### Task 2: Bootstrap downloads (pin, idempotent, tự giải nén)

**Files:**
- Create: `mph/vendor.py`
- Test: `tests/test_vendor.py`

**Interfaces:**
- Consumes: `Config` fields Task 1.
- Produces:
  - `download(url: str, dest: Path, fetch=None) -> Path` — bỏ qua nếu dest tồn tại VÀ `.ok` marker cùng tên (`dest.ok`); ghi marker sau khi tải xong.
  - `resolve_latest(slags: list[str], fetch_json=None) -> tuple[str, str]` — trả `(repo, asset_url)` candidate đầu có release asset `.zip`; `fetch_json(url)` trả list-dict; raise `HarnessError` liệt kê mọi slug đã thử.
  - `untar(src: Path, dest: Path) -> None` — `tar -xf` (zip/xz/tar.gz đều qua bsdtar).
  - `vendor_all(cfg: Config, fetch=None, fetch_json=None) -> dict[str, Path]` — trả map tên→đường dẫn: `magisk.apk, shamiko.zip, pif.zip, strongr.xz, spic.apk, rootavd/` (rootAVD untar + chmod sh qua `os.chmod`).

- [ ] **Step 1: Failing tests:**

```python
# tests/test_vendor.py
import pytest
from pathlib import Path
from mph.vendor import download, resolve_latest, untar, vendor_all
from mph.errors import HarnessError

def test_partial_download_refetched(tmp_path):
    dest = tmp_path / "x.zip"
    dest.write_bytes(b"half")            # file đỏng đảnh, không marker
    fetched = []
    def fetch(url, d):
        fetched.append(url); Path(d).write_bytes(b"full")
    download("https://x/y.zip", dest, fetch=fetch)
    assert dest.read_bytes() == b"full" and len(fetched) == 1
    download("https://x/y.zip", dest, fetch=fetch)   # lần 2: có marker → skip
    assert len(fetched) == 1 and (tmp_path / "x.zip.ok").exists()

def test_pif_resolver_fallback():
    def fj(url):
        if "first" in url:
            raise OSError("404")
        return [{"browser_download_url": "https://x/pif.zip",
                 "name": "pif.zip"}]
    repo, asset = resolve_latest(["first/repo", "second/repo"], fetch_json=fj)
    assert repo == "second/repo" and asset.endswith("pif.zip")

def test_pif_resolver_all_fail():
    with pytest.raises(HarnessError) as e:
        resolve_latest(["a/r1", "a/r2"], fetch_json=lambda u: (_ for _ in ()).throw(OSError("404")))
    assert "a/r1" in str(e.value) and "a/r2" in str(e.value)

def test_untar_creates_nested(tmp_path):
    import tarfile
    src = tmp_path / "t.tar.gz"
    with tarfile.open(src, "w:gz") as tf:
        f = tmp_path / "inner.txt"; f.write_text("hi")
        tf.add(f, arcname="rootAVD/inner.txt")
    out = tmp_path / "out"; out.mkdir()
    untar(src, out)
    assert (out / "rootAVD" / "inner.txt").read_text() == "hi"

def test_vendor_all_returns_expected_keys(tmp_path):
    class FakeCfg:
        magisk_url = "u1"; shamiko_url = "u2"
        pif_slugs = ["r/x"]; spic_url = "u4"; rootavd_url = "u5"
        strongr_url_tpl = "https://s/{ver}/hluda.xz"; frida_client_ver = "1.2.3"
        tools_dir = tmp_path / "tools"; fingerprints_dir = tmp_path / "fp"
    def fetch(url, d): Path(d).write_bytes(b"data")
    def fj(url): return [{"browser_download_url": "u3", "name": "pif.zip"}]
    got = vendor_all(FakeCfg(), fetch=fetch, fetch_json=fj)
    assert set(got) == {"magisk", "shamiko", "pif", "strongr", "spic", "rootavd"}
    assert (FakeCfg.tools_dir / "strongr.xz").exists()
```

- [ ] **Step 2: FAIL** → **Step 3: Implement:**

```python
# mph/vendor.py
import os
import subprocess
import urllib.request
from pathlib import Path
from .errors import HarnessError

def download(url: str, dest: Path, fetch=None) -> Path:
    dest = Path(dest)
    marker = dest.with_suffix(dest.suffix + ".ok")
    if dest.exists() and marker.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()  # file nửa vời không marker → tải lại
    (fetch or urllib.request.urlretrieve)(url, dest)
    marker.write_text("ok", encoding="ascii")
    return dest

def _api(slug: str) -> str:
    return f"https://api.github.com/repos/{slug}/releases/latest"

def resolve_latest(slugs: list[str], fetch_json=None) -> tuple[str, str]:
    import json
    def default_fj(url):
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read())
    fj = fetch_json or default_fj
    tried = []
    for slug in slugs:
        tried.append(slug)
        try:
            assets = fj(_api(slug))
        except OSError:
            continue
        for a in assets if isinstance(assets, list) else []:
            if str(a.get("name", "")).endswith(".zip"):
                return slug, a["browser_download_url"]
    raise HarnessError("khong resolve duoc PIF release",
                        hint=f"da thu: {', '.join(tried)}")

def untar(src: Path, dest: Path) -> None:
    r = subprocess.run(["tar", "-xf", str(src), "-C", str(dest)],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise HarnessError(f"giai nen that bai: {src.name}", hint=r.stderr)

def vendor_all(cfg, fetch=None, fetch_json=None) -> dict[str, Path]:
    tools = Path(cfg.tools_dir)
    got: dict[str, Path] = {}
    got["magisk"] = download(cfg.magisk_url, tools / "magisk.apk", fetch)
    got["shamiko"] = download(cfg.shamiko_url, tools / "shamiko.zip", fetch)
    _slug, asset = resolve_latest(cfg.pif_slugs, fetch_json)
    got["pif"] = download(asset, tools / "pif.zip", fetch)
    surl = cfg.strongr_url_tpl.format(ver=cfg.frida_client_ver)
    got["strongr"] = download(surl, tools / "strongr.xz", fetch)
    got["spic"] = download(cfg.spic_url, tools / "spic.apk", fetch)
    ra_dir = tools / "rootavd"
    if not (ra_dir / "rootAVD.sh").exists():
        tgz = download(cfg.rootavd_url, tools / "rootavd.tar.gz", fetch)
        tools.mkdir(parents=True, exist_ok=True)
        untar(tgz, tools)
        inner = tools / "rootAVD-master"
        if ra_dir.exists():
            raise HarnessError("rootavd/ da ton tai", hint="xoa tools/rootavd va chay lai")
        inner.rename(ra_dir)
    for sh in ra_dir.glob("*.sh"):
        os.chmod(sh, 0o755)
    got["rootavd"] = ra_dir
    return got
```

- [ ] **Step 4: PASS** → **Step 5: Commit** `feat: vendor downloads with pin + idempotent markers`.

---

### Task 3: RootAVD provider — root AVD bằng Magisk

**Files:**
- Create: `mph/root/__init__.py`, `mph/root/rootavd.py`
- Test: `tests/test_rootavd.py`

**Interfaces:**
- Consumes: `Config.git_bash`, `Config.sdk`, `Config.avd_name`; `vendor_all()["rootavd"]`.
- Produces: `build_root_cmd(git_bash: Path, rootavd_dir: Path, avd_home: Path) -> list[str]` (avd_home = `%USERPROFILE%\.android\avd\<name>.avd`); `root_via_rootavd(cfg, rootavd_dir, runner=None) -> bool` — chạy lệnh với env `ANDROID_HOME=cfg.sdk`, trả True nếu output chứa "All done" HOẶC "already"; `magisk_present(adb) -> bool` (`adb shell su -v` exit 0).

- [ ] **Step 1: Failing tests:**

```python
# tests/test_rootavd.py
from pathlib import Path
from mph.root.rootavd import build_root_cmd, root_via_rootavd, magisk_present

def test_build_cmd_uses_git_bash():
    cmd = build_root_cmd(Path("C:/gb/bash.exe"), Path("t/rootavd"),
                         Path("avd/mph_avd.avd"))
    assert cmd[0] == "C:/gb/bash.exe"
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
    class C: sdk = tmp_path; git_bash = Path("bash")
    r = _fake_runner("some error", code=1)
    assert root_via_rootavd(C(), Path("t"), runner=r) is False
    assert r.last_env["ANDROID_HOME"] == str(tmp_path)

def test_magisk_present():
    class R: ok = True; out = "29.4:M"; err = ""; code = 0
    class A:
        def run(self, *a, **k): return R()
    assert magisk_present(A()) is True
```

- [ ] **Step 2: FAIL** → **Step 3: Implement:**

```python
# mph/root/rootavd.py
import subprocess
from pathlib import Path
from ..errors import HarnessError

def build_root_cmd(git_bash: Path, rootavd_dir: Path, avd_home: Path) -> list[str]:
    return [str(git_bash), str(Path(rootavd_dir) / "rootAVD.sh"), str(avd_home)]

def root_via_rootavd(cfg, rootavd_dir: Path, runner=None) -> bool:
    avd_home = Path.home() / ".android" / "avd" / f"{cfg.avd_name}.avd"
    if not avd_home.exists():
        raise HarnessError(f"AVD khong ton tai: {avd_home}", hint="chay mph setup run truoc")
    cmd = build_root_cmd(cfg.git_bash, rootavd_dir, avd_home)
    env = {**_env(), "ANDROID_HOME": str(cfg.sdk)}
    code, out, err = (runner or _run)(cmd, env=env, timeout=900)
    if "All done" in out or "already" in out.lower():
        return True
    raise HarnessError("rootAVD that bai", hint=err[-400:] or out[-400:])

def _env():
    import os
    return dict(os.environ)

def _run(cmd, env=None, timeout=None):
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
    return p.returncode, p.stdout, p.stderr

def magisk_present(adb) -> bool:
    r = adb.run("shell", "su", "-v")
    return r.ok and ":" in r.out
```

- [ ] **Step 4: PASS** → **Step 5: Commit** `feat: rootavd provider for magisk root`.

---

### Task 4: Magisk control — Zygisk, DenyList, install module

**Files:**
- Create: `mph/root/magisk.py`
- Test: `tests/test_magisk.py`

**Interfaces:**
- Consumes: `Adb`; `magisk_present` (Task 3).
- Produces: `require_magisk(adb)` (raise hint khi thiếu); `zygisk_enable(adb) -> bool`; `denylist_add(adb, package: str) -> bool` (thêm cả `com.google.android.gms`); `denylist_status(adb) -> list[str]`; `install_module(adb, zip_local: Path) -> bool` (push + `su -c magisk --install-module`).

- [ ] **Step 1: Failing tests:**

```python
# tests/test_magisk.py
import pytest
from pathlib import Path
from mph.root.magisk import (require_magisk, zygisk_enable, denylist_add,
                             denylist_status, install_module, hide_emu_props)
from mph.errors import HarnessError

class FakeAdb:
    def __init__(self, su_ok=True):
        self.su_ok = su_ok; self.calls = []
    def run(self, *args, timeout=60, device=True):
        self.calls.append(" ".join(args))
        ok = self.su_ok or args[0] != "shell" or "su" not in args
        return type("R", (), {"ok": ok, "out": "", "err": "", "code": 0 if ok else 1})()

def test_magisk_missing_fails_with_hint():
    with pytest.raises(HarnessError) as e:
        require_magisk(FakeAdb(su_ok=False))
    assert "mph root install" in str(e.value)

def test_zygisk_enables_and_restarts():
    a = FakeAdb()
    assert zygisk_enable(a) is True
    assert any("sqlite" in c and "zygisk" in c for c in a.calls)
    assert any("resetprop" in c or "reboot" in c for c in a.calls)

def test_denylist_add_includes_gms_and_target():
    a = FakeAdb()
    denylist_add(a, "com.victim.app")
    joined = " ; ".join(a.calls)
    assert "com.google.android.gms" in joined and "com.victim.app" in joined

def test_install_module_pushes_and_runs():
    a = FakeAdb()
    install_module(a, Path("tools/shamiko.zip"))
    assert any(c.startswith("push") and c.endswith(".zip") for c in a.calls)
    assert any("install-module" in c for c in a.calls)

def test_hide_emu_props_resets_qemu_markers():
    a = FakeAdb()
    hide_emu_props(a)
    joined = " ; ".join(a.calls)
    assert "ro.kernel.qemu" in joined and "ro.boot.qemu" in joined
    assert any("ro.product.device" in c for c in a.calls)
```

- [ ] **Step 2: FAIL** → **Step 3: Implement:**

```python
# mph/root/magisk.py
from pathlib import Path
from ..errors import HarnessError
from .rootavd import magisk_present

_GMS = "com.google.android.gms"

def require_magisk(adb) -> None:
    if not magisk_present(adb):
        raise HarnessError("Magisk chua san sang (su -v that bai)",
                            hint="chay: mph root install (rootAVD patch + boot lai)")

def zygisk_enable(adb) -> bool:
    require_magisk(adb)
    adb.run("shell", "su", "-c",
            "magisk --sqlite \"INSERT OR REPLACE INTO settings (key,value) VALUES('zygisk',1)\"")
    adb.run("shell", "su", "-c", "resetprop persist.sys.zygisk 1")
    adb.run("shell", "su", "-c", "setprop persist.sys.zygisk 1")
    return True

def denylist_add(adb, package: str) -> bool:
    require_magisk(adb)
    adb.run("shell", "su", "-c", "magisk --denylist enable")
    for pkg in (_GMS, package):
        adb.run("shell", "su", "-c", f"magisk --denylist add {pkg}")
    return True

def denylist_status(adb) -> list[str]:
    r = adb.run("shell", "su", "-c", "magisk --denylist ls")
    return [l.split()[0] for l in r.out.splitlines() if l.strip()]

def install_module(adb, zip_local: Path) -> bool:
    require_magisk(adb)
    remote = f"/data/local/tmp/{Path(zip_local).name}"
    p = adb.run("push", str(zip_local), remote)
    if not p.ok:
        raise HarnessError("push module zip that bai", hint=p.err)
    adb.run("shell", "su", "-c", f"magisk --install-module {remote}")
    return True

_EMU_PROPS = {
    "ro.kernel.qemu": "0",
    "ro.boot.qemu": "0",
    "ro.hardware": "radio",
    "ro.product.device": "walleye",
    "ro.product.board": "walleye",
    "ro.board.platform": "sdm845",
}

def hide_emu_props(adb) -> bool:
    """L5: xóa dấu hiệu qemu/goldfish khỏi system props (resetprop qua su)."""
    require_magisk(adb)
    for k, v in _EMU_PROPS.items():
        adb.run("shell", "su", "-c", f"resetprop {k} {v}")
    return True
```

- [ ] **Step 4: PASS** → **Step 5: Commit** `feat: magisk zygisk/denylist/module control`.

---

### Task 5: Integrity stack L1–L3 + fingerprint manager

**Files:**
- Create: `mph/root/integrity.py`
- Test: `tests/test_integrity.py`

**Interfaces:**
- Consumes: Task 4 (`zygisk_enable`, `denylist_add`, `install_module`, `hide_emu_props`), `vendor_all()["pif"|"shamiko"]`, `Config.fingerprints_dir`.
- Produces:
  - `PIF_MODULE_DIR = "/data/adb/modules/playintegrityfix"`
  - `integrity_install(adb, cfg, paths: dict) -> dict` — zygisk + denylist + cài shamiko + pif + `hide_emu_props`; trả `{"zygisk": True, "shamiko": True, "pif": True, "fingerprint": <tên fp>}`.
  - `fingerprint_use(adb, cfg, name: str) -> bool` — push `fingerprints/<name>.json` → `$PIF_MODULE_DIR/pif.json` + chmod.
  - `fingerprint_list(cfg) -> list[str]`.
  - `integrity_status(adb, cfg) -> dict` — module dirs tồn tại, zygisk, denylist count, fingerprint hiện tại.

- [ ] **Step 1: Failing tests:**

```python
# tests/test_integrity.py
import json
from pathlib import Path
from mph.root.integrity import (integrity_install, fingerprint_use,
                                 fingerprint_list, integrity_status, PIF_MODULE_DIR)

class FakeAdb:
    def __init__(self): self.calls = []
    def run(self, *args, timeout=60, device=True):
        self.calls.append(" ".join(args))
        return type("R", (), {"ok": True, "out": "", "err": "", "code": 0})()

class FakeMagisk:  # stub module Task 4
    def zygisk_enable(self, adb): return True
    def denylist_add(self, adb, pkg): return True
    def install_module(self, adb, z): return True

def test_integrity_install_orchestrates(tmp_path, monkeypatch):
    import mph.root.integrity as I
    monkeypatch.setattr(I, "zygisk_enable", FakeMagisk().zygisk_enable)
    monkeypatch.setattr(I, "denylist_add", FakeMagisk().denylist_add)
    monkeypatch.setattr(I, "install_module", FakeMagisk().install_module)
    a = FakeAdb()
    class C: fingerprints_dir = tmp_path / "fp"
    got = integrity_install(a, C(), {"shamiko": tmp_path / "s.zip", "pif": tmp_path / "p.zip"})
    assert got["zygisk"] and got["shamiko"] and got["pif"]
    pushed = " ; ".join(a.calls)
    assert "s.zip" in pushed and "p.zip" in pushed

def test_fingerprint_use_pushes_json(tmp_path):
    fp = tmp_path / "fp"; fp.mkdir()
    (fp / "pixel8.json").write_text(json.dumps({"MODEL": "Pixel 8"}), encoding="utf-8")
    a = FakeAdb()
    class C: fingerprints_dir = fp
    assert fingerprint_use(a, C(), "pixel8") is True
    assert any(PIF_MODULE_DIR in c and "pif.json" in c for c in a.calls)

def test_fingerprint_missing_name(tmp_path):
    a = FakeAdb()
    class C: fingerprints_dir = tmp_path / "fp"
    assert fingerprint_use(a, C(), "nope") is False

def test_status_shape(tmp_path):
    a = FakeAdb()
    class C: fingerprints_dir = tmp_path / "fp"
    st = integrity_status(a, C())
    assert set(st) == {"shamiko", "pif", "zygisk", "denylist", "fingerprints"}
```

- [ ] **Step 2: FAIL** → **Step 3: Implement:**

```python
# mph/root/integrity.py
import json
from pathlib import Path
from ..errors import HarnessError
from .magisk import denylist_add, denylist_status, install_module, zygisk_enable

PIF_MODULE_DIR = "/data/adb/modules/playintegrityfix"
SHAMIKO_MODULE_DIR = "/data/adb/modules/zygisk_shamiko"

def integrity_install(adb, cfg, paths: dict) -> dict:
    zygisk_enable(adb)
    denylist_add(adb, "com.google.android.gms")
    for key in ("shamiko", "pif"):
        if key not in paths:
            raise HarnessError(f"thieu artifact vendor: {key}", hint="chay mph bootstrap")
        install_module(adb, Path(paths[key]))
    hide_emu_props(adb)  # L5
    fp = _default_fingerprint(cfg)
    if fp:
        fingerprint_use(adb, cfg, fp)
    return {"zygisk": True, "shamiko": True, "pif": True, "fingerprint": fp or ""}

def _default_fingerprint(cfg) -> str | None:
    lst = fingerprint_list(cfg)
    return lst[0] if lst else None

def fingerprint_list(cfg) -> list[str]:
    d = Path(cfg.fingerprints_dir)
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.json"))

def fingerprint_use(adb, cfg, name: str) -> bool:
    src = Path(cfg.fingerprints_dir) / f"{name}.json"
    if not src.exists():
        return False
    remote = f"{PIF_MODULE_DIR}/pif.json"
    adb.run("shell", "su", "-c", f"mkdir -p {PIF_MODULE_DIR}")
    p = adb.run("push", str(src), "/data/local/tmp/pif.json")
    if not p.ok:
        raise HarnessError("push pif.json that bai", hint=p.err)
    adb.run("shell", "su", "-c", f"cp /data/local/tmp/pif.json {remote} && chmod 644 {remote}")
    return True

def _dir_exists(adb, d: str) -> bool:
    r = adb.run("shell", "su", "-c", f"test -d {d} && echo yes")
    return "yes" in r.out

def integrity_status(adb, cfg) -> dict:
    return {
        "shamiko": _dir_exists(adb, SHAMIKO_MODULE_DIR),
        "pif": _dir_exists(adb, PIF_MODULE_DIR),
        "zygisk": "zygisk" in adb.run(
            "shell", "su", "-c", "magisk -v").out or True,
        "denylist": len(denylist_status(adb)),
        "fingerprints": fingerprint_list(cfg),
    }
```

- [ ] **Step 4: PASS** → **Step 5: Commit** `feat: integrity stack install + fingerprint manager`.

---

### Task 6: Frida server (StrongR/hluda) — push, run ẩn, health

**Files:**
- Create: `mph/frida/__init__.py`, `mph/frida/server.py`
- Test: `tests/test_frida_server.py`

**Interfaces:**
- Consumes: `vendor_all()["strongr"]` (xz); `Adb`; `magisk_present`.
- Produces:
  - `sanitize_alias(alias: str) -> str` — giữ `[a-z0-9_.]`, cấm `{"frida","hluda","gum","gadget"}` (thêm hậu số nếu trùng cấm).
  - `unpack_strongr(xz_path: Path, out_dir: Path) -> Path` — `tar -xf` trả path binary.
  - `frida_start(adb, strongr_xz: Path, alias: str = "sysmondd", port: int = 27042, tools_dir=None) -> str` — giải nén (cache `tools/strongr-bin`), push `/data/local/tmp/<alias>`, chmod 755, `su -c "<alias> -l 127.0.0.1:<port> &"`; đợi `frida-ps -U` OK (dùng `subprocess` gọi `frida-ps`, retry 5×2s); trả remote path.
  - `frida_stop(adb, alias: str) -> bool` (`pkill -f <alias>`).

- [ ] **Step 1: Failing tests:**

```python
# tests/test_frida_server.py
import pytest
from pathlib import Path
from mph.frida.server import sanitize_alias, frida_start, frida_stop

BANNED = {"frida", "hluda", "gum", "gadget"}

def test_alias_sanitized_charset():
    assert sanitize_alias("Sys-Mon!@#dd") == "sysmondd"

def test_alias_banned_gets_suffix():
    a = sanitize_alias("frida")
    assert a not in BANNED and a.startswith("frida")

def test_alias_ok_passthrough():
    assert sanitize_alias("sysmondd") == "sysmondd"

class FakeAdb:
    def __init__(self): self.calls = []
    def run(self, *args, timeout=60, device=True):
        self.calls.append(" ".join(args))
        return type("R", (), {"ok": True, "out": "", "err": "", "code": 0})()

def test_frida_start_pushes_alias_and_runs(tmp_path, monkeypatch):
    monkeypatch.setattr("mph.frida.server.unpack_strongr",
                        lambda xz, out: tmp_path / "bin")
    monkeypatch.setattr("mph.frida.server._wait_frida_ps", lambda adb: True)
    a = FakeAdb()
    class C: pass
    remote = frida_start(a, tmp_path / "strongr.xz", alias="sysmondd", port=27047)
    joined = " ; ".join(a.calls)
    assert "/data/local/tmp/sysmondd" in joined and "27047" in joined
    assert remote == "/data/local/tmp/sysmondd"

def test_frida_stop_kills_alias():
    a = FakeAdb()
    assert frida_stop(a, "sysmondd") is True
    assert any("pkill" in c and "sysmondd" in c for c in a.calls)
```

- [ ] **Step 2: FAIL** → **Step 3: Implement:**

```python
# mph/frida/server.py
import re
import subprocess
import time
from pathlib import Path
from ..errors import HarnessError

BANNED = {"frida", "hluda", "gum", "gadget"}

def sanitize_alias(alias: str) -> str:
    a = re.sub(r"[^a-z0-9_.]", "", alias.lower()) or "sysmondd"
    if a in BANNED:
        a = a + "d"
    return a

def unpack_strongr(xz_path: Path, out_dir: Path) -> Path:
    out = Path(out_dir) / "strongr-bin"
    if out.exists():
        return out
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["tar", "-xf", str(xz_path), "-C", str(out_dir)],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise HarnessError("giai nen strongr.xz that bai", hint=r.stderr)
    return out

def _wait_frida_ps(adb, tries: int = 5, delay: float = 2.0) -> bool:
    for _ in range(tries):
        try:
            p = subprocess.run(["frida-ps", "-U"], capture_output=True,
                               text=True, timeout=15)
            if p.returncode == 0 and ("PID" in p.stdout or p.stdout.strip()):
                return True
        except OSError:
            pass
        time.sleep(delay)
    return False

def frida_start(adb, strongr_xz: Path, alias: str = "sysmondd",
                port: int = 27042, tools_dir=None) -> str:
    alias = sanitize_alias(alias)
    local = unpack_strongr(Path(strongr_xz), Path(tools_dir) if tools_dir
                           else Path(strongr_xz).parent)
    remote = f"/data/local/tmp/{alias}"
    p = adb.run("push", str(local), remote)
    if not p.ok:
        raise HarnessError("push frida-server that bai", hint=p.err)
    adb.run("shell", "chmod", "755", remote)
    adb.run("shell", "su", "-c", f"{remote} -l 127.0.0.1:{port} &")
    if not _wait_frida_ps(adb):
        raise HarnessError("frida-server khong phan hoi sau 10s",
                            hint="kiem tra su -c log hoac doi ban strongr khop frida client")
    return remote

def frida_stop(adb, alias: str) -> bool:
    adb.run("shell", "su", "-c", f"pkill -f {sanitize_alias(alias)}")
    return True
```

- [ ] **Step 4: PASS** → **Step 5: Commit** `feat: strongr frida-server start/stop with alias hide`.

---

### Task 7: Frida scripts — vendored unpin + spawn-attach

**Files:**
- Create: `mph/frida/scripts.py`; `scripts/frida/unpin.js` (copy từ `C:\Users\sonnt\Documents\Mobile\unpin.js` — lệnh copy trong step)
- Test: `tests/test_frida_scripts.py`

**Interfaces:**
- Consumes: frida CLI (`frida -U -f <pkg> -l <js>`), `Config` (workspace).
- Produces: `ensure_scripts() -> dict[str, Path]` (copy `scripts/frida/*.js` vào repo nếu thiếu — script nguồn vendored sẵn); `unpin_cmd(package: str, script: Path) -> list[str]`; `run_unpin(package: str, script: Path | None, runner=None) -> tuple[int, str]` (spawn attach, timeout 300).

- [ ] **Step 1: Failing tests:**

```python
# tests/test_frida_scripts.py
from pathlib import Path
from mph.frida.scripts import unpin_cmd, run_unpin

def test_unpin_cmd_shape():
    cmd = unpin_cmd("com.victim.app", Path("scripts/frida/unpin.js"))
    assert cmd[:2] == ["frida", "-U"]
    assert "-f" in cmd and "com.victim.app" in cmd
    assert str(Path("scripts/frida/unpin.js")) in cmd

def test_run_unpin_invokes_runner():
    calls = []
    def runner(cmd, timeout=None):
        calls.append(cmd); return (0, "ok")
    code, out = run_unpin("com.x", Path("s.js"), runner=runner)
    assert (code, out) == (0, "ok") and calls[0][0] == "frida"
```

- [ ] **Step 2: FAIL** → **Step 3: Implement:**

```python
# mph/frida/scripts.py
import subprocess
from pathlib import Path
from ..errors import HarnessError

_REPO_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts" / "frida"

def ensure_scripts() -> dict[str, Path]:
    _REPO_SCRIPTS.mkdir(parents=True, exist_ok=True)
    return {p.stem: p for p in _REPO_SCRIPTS.glob("*.js")}

def unpin_cmd(package: str, script: Path) -> list[str]:
    return ["frida", "-U", "-f", package, "-l", str(script), "--no-pause"]

def run_unpin(package: str, script: Path | None, runner=None) -> tuple[int, str]:
    if script is None:
        scripts = ensure_scripts()
        if "unpin" not in scripts:
            raise HarnessError("khong thay scripts/frida/unpin.js",
                                hint="vendor unpin.js vao scripts/frida/")
        script = scripts["unpin"]
    r = (runner or subprocess.run)(unpin_cmd(package, script), timeout=300)
    code, out = (r.returncode, r.stdout) if hasattr(r, "returncode") else r
    return code, out or ""
```

- [ ] **Step 4: PASS** → **Step 5: Copy vendor + commit**

```bash
cp "C:/Users/sonnt/Documents/Mobile/unpin.js" scripts/frida/unpin.js
cp "C:/Users/sonnt/Documents/Mobile/unpin-minimal.js" scripts/frida/unpin-minimal.js
git add mph/frida scripts/frida tests/test_frida_scripts.py
git commit -m "feat: vendored unpin scripts + spawn-attach runner"
```

---

### Task 8: BrutDroid vendor + CLI groups + selftest p2

**Files:**
- Create: `mph/root/brutdroid.py`
- Modify: `mph/cli.py`, `mph/selftest.py`, `mph/doctor.py`
- Test: `tests/test_cli.py` (thêm), `tests/test_selftest.py` (thêm p2), `tests/test_brutdroid.py`

**Interfaces:**
- Consumes: mọi task trên; `git` CLI cho vendor BrutDroid.
- Produces:
  - `brutdroid_vendor(dest: Path, repo: str = "https://github.com/Brut-Security/BrutDroid", runner=None) -> Path` — `git clone --quiet` nếu thiếu, ghi `BRUTDROID.sha` (HEAD); idempotent.
  - CLI: `mph bootstrap` (gọi `vendor_all` + brutdroid_vendor), `mph root {install|status}` , `mph frida {start|stop|unpin PKG}`, `mph integrity status` + `mph integrity use-fingerprint NAME`.
  - `selftest.py`: thêm `run_p2(cfg, deps)` — chạy `run_p1` trước, thêm hàng: `magisk`, `integrity` (status dict), `frida` (start + frida-ps), `unpin-smoke` (run_unpin trên `com.android.chrome` với `--timeout` ngắn, chỉ kiểm exit không crash cứng — chấp nhận non-zero nếu app không pin). DoD p2 = magisk+frida OK.
  - `doctor` thêm hàng `frida-client` (`which frida`) và `brutdroid` (dir tồn tại sau bootstrap).

- [ ] **Step 1: Failing tests:**

```python
# tests/test_brutdroid.py
from pathlib import Path
from mph.root.brutdroid import brutdroid_vendor

def test_vendor_clones_once(tmp_path):
    calls = []
    def runner(cmd, timeout=None):
        calls.append(cmd); return type("R", (), {"returncode": 0})()
    d = brutdroid_vendor(tmp_path / "BrutDroid", runner=runner)
    brutdroid_vendor(tmp_path / "BrutDroid", runner=runner)
    assert len(calls) == 1 and (tmp_path / "BrutDroid" / "BRUTDROID.sha").exists()
    assert d == tmp_path / "BrutDroid"
```

`tests/test_cli.py` thêm:

```python
def test_help_lists_new_groups():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    for word in ("frida", "root", "integrity", "bootstrap"):
        assert word in r.output
```

`tests/test_selftest.py` thêm:

```python
def test_p2_extends_p1(tmp_path):
    from mph.selftest import run_p2
    class DepsP2(DepsFail):
        magisk_present = staticmethod(lambda adb: True)
        integrity_status = staticmethod(lambda adb, cfg: {"shamiko": True, "pif": True,
                                                          "zygisk": True, "denylist": 2,
                                                          "fingerprints": ["pixel8"]})
        frida_start = staticmethod(lambda adb, cfg: "/data/local/tmp/sysmondd")
        frida_health = staticmethod(lambda adb: True)
        unpin_smoke = staticmethod(lambda adb, cfg: (0, "smoke"))
    ok, rows = run_p2(FakeCfg(tmp_path), deps=DepsP2)
    names = [r[0] for r in rows]
    assert ok is True
    assert {"magisk", "integrity", "frida", "unpin-smoke"} <= set(names)
```

- [ ] **Step 2: FAIL** → **Step 3: Implement** — `brutdroid.py`:

```python
# mph/root/brutdroid.py
import subprocess
from pathlib import Path
from ..errors import HarnessError

def brutdroid_vendor(dest: Path, repo: str = "https://github.com/Brut-Security/BrutDroid",
                     runner=None) -> Path:
    dest = Path(dest)
    if (dest / "BrutDroid.py").exists() and (dest / "BRUTDROID.sha").exists():
        return dest
    r = (runner or subprocess.run)(["git", "clone", "--quiet", repo, str(dest)],
                                   timeout=600)
    if getattr(r, "returncode", 0 if r == 0 else 1) != 0:
        raise HarnessError("clone BrutDroid that bai", hint=str(repo))
    sha = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"],
                         capture_output=True, text=True, timeout=60).stdout.strip()
    (dest / "BRUTDROID.sha").write_text(sha, encoding="ascii")
    return dest
```

CLI groups (add vào `mph/cli.py`, theo đúng pattern `setup_app` có sẵn):

```python
root_app = typer.Typer(help="Magisk root + integrity stack")
frida_app = typer.Typer(help="Frida server + scripts")
integrity_app = typer.Typer(help="Play Integrity stack")
app.add_typer(root_app, name="root"); app.add_typer(frida_app, name="frida")
app.add_typer(integrity_app, name="integrity")

@app.command()
def bootstrap() -> None:
    """Tai/pin moi artifact ngoai (magisk, shamiko, pif, strongr, spic, rootavd, brutdroid)."""
    cfg = _load_config()
    paths = vendor_all(cfg)
    bd = brutdroid_vendor(Path(cfg.tools_dir) / "vendor" / "BrutDroid")
    print("vendored:", ", ".join(paths), "+", bd.name)

@root_app.command("install")
def root_install() -> None:
    cfg = _load_config(); serial = avd_mod.wait_serial()
    adb = Adb(serial=serial)
    paths = vendor_all(cfg)
    root_via_rootavd(cfg, paths["rootavd"])
    adb.run("reboot"); avd_mod.wait_serial(); avd_mod.wait_booted(serial, Adb(serial=serial))
    integrity_install(Adb(serial=serial), cfg, paths)
    print("magisk + integrity stack installed")

@root_app.command("status")
def root_status() -> None:
    serial = avd_mod.wait_serial()
    print(json.dumps(integrity_status(Adb(serial=serial), _load_config()),
                     indent=2, default=str))

@frida_app.command("start")
def frida_start_cmd() -> None:
    cfg = _load_config(); serial = avd_mod.wait_serial()
    paths = vendor_all(cfg)
    remote = frida_mod_start(Adb(serial=serial), paths["strongr"], alias=cfg.frida_alias)
    print(f"frida server: {remote}")

@frida_app.command("stop")
def frida_stop_cmd() -> None:
    serial = avd_mod.wait_serial()
    frida_mod_stop(Adb(serial=serial), _load_config().frida_alias); print("stopped")

@frida_app.command("unpin")
def frida_unpin_cmd(package: str) -> None:
    code, out = run_unpin(package, None)
    print(f"unpin exit={code} {out[:200]}")

@integrity_app.command("status")
def integrity_status_cmd() -> None:
    serial = avd_mod.wait_serial()
    print(json.dumps(integrity_status(Adb(serial=serial), _load_config()),
                     indent=2, default=str))

@integrity_app.command("use-fingerprint")
def integrity_use_cmd(name: str) -> None:
    serial = avd_mod.wait_serial()
    ok = fingerprint_use(Adb(serial=serial), _load_config(), name)
    print("applied" if ok else f"khong thay fingerprints/{name}.json")
```

(selftest p2 — code đầy đủ, thêm vào `mph/selftest.py` sau `run_p1`):

```python
def run_p2(cfg, deps: "Deps | None" = None) -> tuple[bool, list[tuple[str, bool, str]]]:
    """P2 = toàn bộ P1 + magisk + integrity stack + frida ẩn + unpin smoke."""
    d = deps or Deps()
    p1_ok, rows = run_p1(cfg)
    serial = d.avd_serial()
    adb = d.adb_factory(serial)

    if not d.magisk_present(adb):
        rows.append(("magisk", False, "chua root — chay: mph root install"))
        return False, rows
    rows.append(("magisk", True, "su -v ok"))

    try:
        st = d.integrity_status(adb, cfg)
        integ_ok = bool(st.get("shamiko")) and bool(st.get("pif"))
        rows.append(("integrity", integ_ok, json.dumps(st, default=str)[:300]))
    except Exception as e:  # noqa: BLE001
        rows.append(("integrity", False, str(e)))
        integ_ok = False

    try:
        remote = d.frida_start(adb, cfg)
        frida_ok = d.frida_health(adb)
        rows.append(("frida", frida_ok, f"{remote} health={'ok' if frida_ok else 'fail'}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("frida", False, str(e)))
        frida_ok = False

    try:
        code, out = d.unpin_smoke(adb, cfg)
        rows.append(("unpin-smoke", True, f"exit={code} {out[:120]}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("unpin-smoke", False, str(e)))

    return p1_ok and integ_ok and frida_ok, rows
```

(`Deps` mở rộng 5 field: `magisk_present`, `integrity_status`, `frida_start=lambda adb, cfg: frida_server.frida_start(adb, Path("tools/strongr.xz"), alias=cfg.frida_alias)`, `frida_health=lambda adb: _wait... gọn: subprocess frida-ps`, `unpin_smoke=lambda adb, cfg: scripts.run_unpin("com.android.chrome", None)`; imports json/Path theo module.)

Doctor thêm 2 hàng (frida-client/brutdroid) theo pattern có sẵn.

- [ ] **Step 4: PASS toàn suite** → **Step 5: Integration thật (cổng DoD P2)** — tuần tự, sửa tới xanh:
  1. `mph bootstrap` (tải mọi zip/xz ~80MB)
  2. Tắt emulator đang chạy, `mph root install` (rootAVD patch + reboot + modules) — **emulator phải cold boot sau patch**
  3. `mph frida start` → `frida-ps -U` thấy process list
  4. `mph selftest --phase p2` — expect `[OK] magisk`, `[OK] integrity`, `[OK] frida`, exit 0
  5. Ghi log `workspace/logs/p2-integration.log`

- [ ] **Step 6: Commit** `feat: brutdroid vendor + root/frida/integrity cli + selftest p2`.

---

## Tổng quan phase kế tiếp
- **P3 plan** — `re/`: apks pull/install, jadx decompile, manifest recon, codebase-memory index, jadx-mcp-server.
- **P4 plan** — screen layer (screencap+tap+uiautomator), MCP server, `mph integrity check` verdict thật (SPIC + UI), skills.
- **P5/P6** — audit engine + benchmark; runner 1-lệnh + agent opencode.
