# Mobile Pentest Harness — P1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng nền mobile-harness P1: repo + config + bootstrap SDK/AVD + Burp start/MCP client + CA hệ thống + route proxy + `mph selftest --phase p1` xanh tới "HTTPS 200 qua Burp từ trong emulator".

**Architecture:** Python package `mph` (Typer CLI) điều phối công cụ có sẵn (adb, emulator, Burp Pro). Mọi lệnh idempotent, state nằm trong `workspace/`, version pin trong `mph.toml`. Không AI ở tầng này.

**Tech Stack:** Python 3.12, Typer, cryptography, pytest (unit) + selftest tích hợp trên AVD thật.

**Spec:** `docs/superpowers/specs/2026-10-07-mobile-pentest-harness-design.md` (§3 kiến trúc, §4.2 proxy, §8 error, §9 testing, §10 roadmap P1).

**Tinh chỉnh so với roadmap spec (có lý do):** P1 root bằng `adb root` + `adb remount` (image google_apis cho phép, đủ cài CA hệ thống) — không cần RootAVD/Magisk/BrutDroid cho DoD P1. RootAVD + Magisk + module + vendored BrutDroid chuyển trọn sang P2. Mọi hàm root/CA viết sẵn interface để P2 cắm thêm không sửa P1.

## Global Constraints

- Windows 11; chạy được từ cả PowerShell lẫn Git Bash. ADB lấy từ PATH (`C:\Program Files\scrcpy\adb.exe`), SDK tại `%LOCALAPPDATA%\Android\Sdk` (env `ANDROID_HOME` override).
- Burp: `C:\Program Files\Burp\bin\BurpSuitePro` (resolver dò `.exe`/`.bat`). Proxy port **8080**, Burp MCP port **9876**.
- AVD workhorse: name `mph_avd`, image `system-images;android-34;google_apis;x86_64`.
- Idempotent: chạy lần 2 không tải lại/ổn định. Immutability: config object không mutate; lỗi raise `HarnessError(msg, hint=...)`, không nuốt âm thầm.
- File < 400 dòng, hàm < 50 dòng. Conventional commits, không attribution footer.
- Deps P1 chỉ: `typer`, `cryptography`, `pytest`. KHÔNG thêm fastmcp/frida/pillow (P2/P4).

## Review Focus

1. **Burp sai đường dẫn / không mở được port** → `start` phải timeout có bảng điều khiển (hint đường resolver đã dò), không treo vĩnh viễn. Test: Task 5 `test_wait_port_timeout`.
2. **Device offline giữa chừng** ("device offline"/"not found" stderr) → retry 3 lần backoff 0.5/1/2s rồi mới fail. Test: Task 2 `test_retry_transient`.
3. **Sai hash tên file CA** (thuật toán openssl subject_hash cũ MD5) → HTTPS vẫn fail dù cert đã push. Test: Task 7 fixture pin chuỗi hash đúng format hex 8 ký tự + selftest phân biệt "cert không tin" vs "không nối được".
4. **Chạy lại lần 2** (AVD đã có, Burp project cũ, cert đã cài) → mọi lệnh vẫn xanh không hỏi. Test: Task 4 `test_create_avd_force`, Task 7 `test_install_overwrites`.
5. **Burp MCP SSE không trả endpoint event** (MCP chưa bật trong Burp) → client trả lỗi cấu trúc sau timeout 10s, không treo. Test: Task 6 `test_no_endpoint_event`.

---

### Task 1: Scaffold repo + config + errors

**Files:**
- Create: `pyproject.toml`, `mph.toml`, `mph/__init__.py`, `mph/config.py`, `mph/errors.py`, `README.md`, `.gitignore`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `HarnessError(msg, hint="")`, `load_config(path: Path | None = None) -> Config` với fields: `Config.sdk: Path`, `Config.burp_exe: Path`, `Config.git_bash: Path`, `Config.avd_name: str`, `Config.image: str`, `Config.proxy_port: int` (8080), `Config.burp_mcp_port: int` (9876), `Config.workspace: Path`. Env override: `ANDROID_HOME`, `BURP_PATH`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_config.py
import pytest
from mph.config import load_config, Config
from mph.errors import HarnessError

def test_load_defaults(tmp_path):
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
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python -m pytest tests/test_config.py -v`
Expected: `ModuleNotFoundError: No module named 'mph'`

- [ ] **Step 3: Implement**

```python
# pyproject.toml
[project]
name = "mph"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["typer>=0.12", "cryptography>=42"]
[project.scripts]
mph = "mph.cli:app"
[tool.pytest.ini_options]
testpaths = ["tests"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

```toml
# mph.toml — mọi pin ở đây
[paths]
sdk = 'C:/Users/sonnt/AppData/Local/Android/Sdk'
git_bash = 'C:/Program Files/Git/bin/bash.exe'

[avd]
name = "mph_avd"
image = "system-images;android-34;google_apis;x86_64"

[proxy]
port = 8080
burp_mcp_port = 9876

[workspace]
root = "workspace"
```

```python
# mph/errors.py
class HarnessError(Exception):
    def __init__(self, msg: str, hint: str = ""):
        super().__init__(msg if not hint else f"{msg} | hint: {hint}")
        self.hint = hint
```

```python
# mph/config.py
from dataclasses import dataclass, replace
from pathlib import Path
import os, tomllib
from .errors import HarnessError

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_TOML = _REPO_ROOT / "mph.toml"

@dataclass(frozen=True)
class Config:
    sdk: Path
    burp_exe: Path
    git_bash: Path
    avd_name: str
    image: str
    proxy_port: int
    burp_mcp_port: int
    workspace: Path

def _resolve_burp() -> Path:
    if os.environ.get("BURP_PATH"):
        return Path(os.environ["BURP_PATH"])
    for c in (r"C:\Program Files\Burp\bin\BurpSuitePro.exe",
              r"C:\Program Files\Burp\bin\BurpSuitePro.bat",
              r"C:\Program Files\Burp\bin\BurpSuitePro\BurpSuitePro.exe"):
        if Path(c).exists():
            return Path(c)
    raise HarnessError("khong tim thay Burp Suite Pro", hint="dat env BURP_PATH tro den exe Burp")

def load_config(path: Path | None = None) -> Config:
    data: dict = {}
    f = path or _DEFAULT_TOML
    if f.exists():
        data = tomllib.loads(f.read_text(encoding="utf-8"))
    p = data.get("paths", {})
    avd = data.get("avd", {})
    px = data.get("proxy", {})
    sdk = Path(os.environ.get("ANDROID_HOME") or p.get("sdk", r"C:\Users\sonnt\AppData\Local\Android\Sdk"))
    return Config(
        sdk=sdk,
        burp_exe=_resolve_burp(),
        git_bash=Path(p.get("git_bash", r"C:\Program Files\Git\bin\bash.exe")),
        avd_name=avd.get("name", "mph_avd"),
        image=avd.get("image", "system-images;android-34;google_apis;x86_64"),
        proxy_port=int(px.get("port", 8080)),
        burp_mcp_port=int(px.get("burp_mcp_port", 9876)),
        workspace=_REPO_ROOT / data.get("workspace", {}).get("root", "workspace"),
    )
```

`.gitignore`: `tools/`, `workspace/`, `__pycache__/`, `*.egg-info/`, `.pytest_cache/`. `README.md`: một đoạn mô tả + ràng buộc "chỉ dùng cho app được ủy quyền" (nội dung spec §1).

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest tests/test_config.py -v`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml mph.toml mph tests README.md .gitignore
git commit -m "feat: scaffold mph package with pinned config and error type"
```

---

### Task 2: ADB wrapper (serial-aware, retry, devices parse)

**Files:**
- Create: `mph/device/adb.py`, `mph/device/__init__.py`
- Test: `tests/test_adb.py`

**Interfaces:**
- Consumes: `Config` (Task 1).
- Produces: `AdbResult(ok: bool, out: str, err: str, code: int)`; `Adb(serial: str | None, adb_path: str, retries: int = 3).run(*args, timeout: float = 60, device: bool = True) -> AdbResult`; `Adb.devices(adb_path) -> list[tuple[str, str]]` (serial, state). Transient stderr patterns: `("device offline", "device not found", "closed", "timeout")`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_adb.py
from mph.device.adb import Adb, AdbResult

def _fake_run(results):
    calls = []
    def runner(cmd, timeout=None):
        calls.append(cmd)
        return results.pop(0)
    return calls, runner

def test_cmd_includes_serial():
    calls, runner = _fake_run([(0, "ok", "")])
    a = Adb(serial="emulator-5554", runner=runner)
    a.run("shell", "true")
    assert calls[0][:4] == ["adb", "-s", "emulator-5554", "shell"]

def test_retry_transient_then_ok():
    calls, runner = _fake_run([(1, "", "device offline"), (0, "ok", "")])
    a = Adb(serial="e", runner=runner, sleeper=lambda s: None)
    r = a.run("shell", "true")
    assert r.ok and len(calls) == 2

def test_retry_exhausted():
    calls, runner = _fake_run([(1, "", "device offline")] * 3)
    a = Adb(serial="e", runner=runner, sleeper=lambda s: None)
    r = a.run("shell", "true")
    assert not r.ok and len(calls) == 3

def test_no_retry_on_normal_error():
    calls, runner = _fake_run([(1, "", "Unknown command")])
    a = Adb(serial="e", runner=runner, sleeper=lambda s: None)
    a.run("bogus")
    assert len(calls) == 1

def test_devices_parse(monkeypatch):
    sample = ("List of devices attached\n"
              "emulator-5554\tdevice product:sdk_phone64_x86_64 transport_id:1\n"
              "a35d6a420508\tdevice product:selene transport_id:2\n\n")
    monkeypatch.setattr("mph.device.adb._raw_run", lambda cmd, timeout=None: (0, sample, ""))
    devs = Adb.devices()
    assert devs == [("emulator-5554", "device"), ("a35d6a420508", "device")]
```

- [ ] **Step 2: Run — expect FAIL** (`python -m pytest tests/test_adb.py -v`)

- [ ] **Step 3: Implement**

```python
# mph/device/adb.py
import subprocess, time
from dataclasses import dataclass

TRANSIENT = ("device offline", "device not found", "closed", "timeout")

def _raw_run(cmd: list[str], timeout: float | None = None):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr

@dataclass(frozen=True)
class AdbResult:
    ok: bool; out: str; err: str; code: int

class Adb:
    def __init__(self, serial: str | None = None, adb_path: str = "adb",
                 retries: int = 3, runner=_raw_run, sleeper=time.sleep):
        self.serial, self.adb_path = serial, adb_path
        self.retries, self._run, self._sleep = retries, runner, sleeper

    def run(self, *args: str, timeout: float = 60, device: bool = True) -> AdbResult:
        cmd = [self.adb_path] + (["-s", self.serial] if (self.serial and device) else []) + list(args)
        last: AdbResult | None = None
        for attempt in range(self.retries):
            code, out, err = self._run(cmd, timeout=timeout)
            last = AdbResult(code == 0, out, err, code)
            if last.ok or not any(t in err.lower() for t in TRANSIENT):
                return last
            if attempt < self.retries - 1:
                self._sleep(0.5 * (2 ** attempt))
        assert last is not None
        return last

    @staticmethod
    def devices(adb_path: str = "adb") -> list[tuple[str, str]]:
        _, out, _ = _raw_run([adb_path, "devices"])
        devs = []
        for line in out.splitlines()[1:]:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] != "attached":
                devs.append((parts[0], parts[1]))
        return devs
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit** — `git commit -m "feat: adb wrapper with serial, transient retry, device listing"`

---

### Task 3: `mph doctor` — kiểm tra môi trường

**Files:**
- Create: `mph/cli.py`, `mph/doctor.py`
- Modify: `mph/__init__.py` (export)
- Test: `tests/test_doctor.py`

**Interfaces:**
- Consumes: `Config`, `Adb.devices`.
- Produces: `check_env(cfg: Config, probes: Probes) -> list[tuple[str, bool, str]]`; CLI `mph doctor`. `Probes` là dataclass các callable mặc định (`exists`, `which`, `devices`) để test tiêm fake.

- [ ] **Step 1: Failing tests**

```python
# tests/test_doctor.py
from pathlib import Path
from mph.doctor import check_env, Probes

def make_cfg(tmp_path, **kw):
    from mph.config import Config
    d = dict(sdk=tmp_path/"Sdk", burp_exe=tmp_path/"burp.exe", git_bash=tmp_path/"bash.exe",
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
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
# mph/doctor.py
import shutil
from dataclasses import dataclass
from .config import Config

@dataclass(frozen=True)
class Probes:
    exists: staticmethod = staticmethod(lambda p: __import__("pathlib").Path(p).exists())
    which: staticmethod = staticmethod(shutil.which)
    devices: staticmethod = staticmethod(lambda: [])

def check_env(cfg: Config, probes: Probes | None = None) -> list[tuple[str, bool, str]]:
    p = probes or Probes()
    rows: list[tuple[str, bool, str]] = [
        ("adb", p.which("adb") is not None, "cai dat platform-tools hoac them scrcpy vao PATH"),
        ("android-sdk", p.exists(cfg.sdk), f"dat ANDROID_HOME — khong thay {cfg.sdk}"),
        ("emulator", p.exists(cfg.sdk / "emulator" / "emulator.exe"), "sdkmanager 'emulator'"),
        ("burp", p.exists(cfg.burp_exe), "dat env BURP_PATH"),
        ("git-bash", p.exists(cfg.git_bash), "cai Git for Windows"),
    ]
    devs = p.devices()
    rows.append(("device", len(devs) > 0, "mph avd boot de tao device"))
    return rows
```

```python
# mph/cli.py
import typer
from .config import load_config
from .doctor import check_env, Probes
from .device.adb import Adb

app = typer.Typer(help="Mobile Pentest Harness", no_args_is_help=True)

@app.command()
def doctor() -> None:
    """Kiem tra moi thanh phan moi truong can cho harness."""
    rows = check_env(load_config(), Probes(devices=lambda: Adb.devices()))
    bad = 0
    for name, ok, hint in rows:
        mark = "OK " if ok else "FAIL"
        print(f"[{mark}] {name}" + ("" if ok else f" — {hint}"))
        bad += 0 if ok else 1
    raise typer.Exit(code=1 if bad else 0)
```

- [ ] **Step 4: Run tests + smoke thật**

Run: `python -m pytest tests/test_doctor.py -v` rồi `python -m mph.cli doctor` (hoặc `python -c "from mph.cli import app; app()" doctor`).
Expected: tests PASS; doctor in ít nhất `[OK] adb` (scrcpy trên PATH).

- [ ] **Step 5: Commit** — `feat: mph doctor environment check`

---

### Task 4: Bootstrap SDK — cmdline-tools, system image, tạo AVD

**Files:**
- Create: `mph/bootstrap.py`, `mph/device/avd.py`
- Test: `tests/test_bootstrap.py`

**Interfaces:**
- Consumes: `Config`.
- Produces:
  - `ensure_cmdline_tools(sdk: Path, cache: Path, fetch=urllib.request.urlretrieve) -> Path` — trả `sdk/cmdline-tools/latest`, idempotent.
  - `CMDLINE_TOOLS_URL = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"` (pin; override bằng tham số).
  - `install_image(sdk: Path, image: str, runner) -> None` — sdkmanager licenses + install.
  - `create_avd(sdk: Path, name: str, image: str, runner) -> None` — avdmanager, `--force` (idempotent).
  - `avd_boot(sdk: Path, name: str, runner_popen) -> None`, `avd_serial() -> str | None` (dò `emulator-XXXX` từ `Adb.devices()`).

- [ ] **Step 1: Failing tests**

```python
# tests/test_bootstrap.py
from pathlib import Path
from mph.bootstrap import ensure_cmdline_tools, CMDLINE_TOOLS_URL, install_image, create_avd

def test_cmdline_tools_idempotent(tmp_path, monkeypatch):
    downloads = []
    def fake_fetch(url, dest):
        downloads.append(url)
        z = Path(dest).parent / "tools.zip"
        import zipfile
        with zipfile.ZipFile(z, "w") as zf:      # giả lập cấu trúc zip thật
            zf.writestr("cmdline-tools/bin/sdkmanager.bat", "@echo off")
        Path(dest).write_bytes(z.read_bytes())
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
    def runner(cmd, timeout=None):
        calls.append(cmd); return (0, "ok", "")
    create_avd(tmp_path, "mph_avd", "system-images;android-34;google_apis;x86_64", runner)
    create_avd(tmp_path, "mph_avd", "system-images;android-34;google_apis;x86_64", runner)
    assert calls[0][:3] == ["avdmanager", "create", "avd"]
    assert all("--force" in c for c in calls) and len(calls) == 2
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement** (đường dẫn `bin` nối thêm `;` để Windows tìm `sdkmanager.bat`)

```python
# mph/bootstrap.py
import os, subprocess, urllib.request, zipfile, io
from pathlib import Path
from .errors import HarnessError

CMDLINE_TOOLS_URL = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"

def ensure_cmdline_tools(sdk: Path, cache: Path, fetch=urllib.request.urlretrieve,
                         unzip=None) -> Path:
    dest = sdk / "cmdline-tools" / "latest"
    marker = dest / "bin" / "sdkmanager.bat"
    if marker.exists():
        return dest
    cache.mkdir(parents=True, exist_ok=True)
    z = cache / "cmdline-tools.zip"
    if not z.exists():
        fetch(CMDLINE_TOOLS_URL, z)
    sdk.mkdir(parents=True, exist_ok=True)
    tmp_extract = sdk / "_cmdline_tmp"
    if unzip:
        unzip(z, tmp_extract)
    else:
        with zipfile.ZipFile(z) as zf:
            zf.extractall(tmp_extract)
    # zip có thư mục gốc "cmdline-tools" → đổi tên thành "latest"
    inner = tmp_extract / "cmdline-tools"
    if dest.exists():
        raise HarnessError("cmdline-tools/latest da ton tai", hint="xoa thu muc va chay lai")
    inner.rename(dest)
    for f in tmp_extract.glob("*"):
        f.unlink()
    tmp_extract.rmdir()
    return dest

def _sdkmanager(sdk: Path) -> str:
    return str(sdk / "cmdline-tools" / "latest" / "bin" / "sdkmanager.bat")

def install_image(sdk: Path, image: str, runner=subprocess.run) -> None:
    env = {**os.environ, "ANDROID_HOME": str(sdk)}
    # Windows không có pipe `yes` → dùng input
    lic = runner([_sdkmanager(sdk), "--sdk_root=" + str(sdk), "--licenses"],
                 input="y\n" * 20, text=True, timeout=600)
    ins = runner([_sdkmanager(sdk), "--sdk_root=" + str(sdk), image], timeout=3600)
    if ins.returncode != 0:
        raise HarnessError("cai system image that bai", hint=f"sdkmanager output: {ins.stdout[-500:]}")

def create_avd(sdk: Path, name: str, image: str, runner=subprocess.run) -> None:
    avdm = str(sdk / "cmdline-tools" / "latest" / "bin" / "avdmanager.bat")
    r = runner([avdm, "create", "avd", "-n", name, "-k", image, "-d", "pixel_6", "--force"],
               timeout=120)
    if r.returncode != 0:
        raise HarnessError("tao AVD that bai", hint=f"avdmanager: {r.stderr[-500:]}")
```

```python
# mph/device/avd.py
import subprocess
from pathlib import Path
from .adb import Adb

def avd_boot(sdk: Path, name: str, runner_popen=subprocess.Popen) -> None:
    emu = sdk / "emulator" / "emulator.exe"
    if not emu.exists():
        raise HarnessError("khong co emulator.exe", hint="sdkmanager emulator")
    existing = avd_serial()
    if existing:
        return
    runner_popen([str(emu), "-avd", name, "-no-snapshot-load", "-no-boot-anim"],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def avd_serial() -> str | None:
    for serial, _state in Adb.devices():
        if serial.startswith("emulator-"):
            return serial
    return None

def wait_booted(serial: str, adb: Adb, timeout: float = 300) -> bool:
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = adb.run("shell", "getprop", "sys.boot_completed", timeout=15)
        if r.ok and r.out.strip() == "1":
            return True
        time.sleep(3)
    return False
```

Lưu ý: `install_image` chấp nhận `input=`/`text=` kwargs — runner giả trong test dùng `def runner(cmd, timeout=None, **kw)`.

- [ ] **Step 4: Run — expect PASS** (`python -m pytest tests/test_bootstrap.py -v`)

- [ ] **Step 5: Integration thật (manual gate, không tự động):** `python -c "from mph.cli import app; app()" bootstrap` sau khi Task 6 wire CLI. Ghi kết quả vào `workspace/logs/bootstrap.log`.

- [ ] **Step 6: Commit** — `feat: sdk bootstrap (cmdline-tools, image, avd create/boot)`

---

### Task 5: Burp — resolver, listener config, start, wait-for-port

**Files:**
- Create: `mph/proxy/burp.py`, `mph/proxy/__init__.py`
- Test: `tests/test_burp.py`

**Interfaces:**
- Consumes: `Config.burp_exe`, `Config.proxy_port`.
- Produces:
  - `listener_config(port: int) -> dict` — đúng schema `project_options.proxy.request_listeners[]` (mẫu spec §2).
  - `wait_port(port: int, timeout: float = 60, poller=None) -> bool`.
  - `burp_start(cfg: Config, project_file: Path, config_file: Path, popen=subprocess.Popen) -> int` (pid) — raise `HarnessError` nếu exe thiếu; nếu port đã mở → trả `-1` (đang chạy, idempotent).

- [ ] **Step 1: Failing tests**

```python
# tests/test_burp.py
import socket, threading, json
from mph.proxy.burp import listener_config, wait_port, burp_start

def test_listener_config_shape():
    c = listener_config(8080)
    lst = c["project_options"]["proxy"]["request_listeners"][0]
    assert lst == {"listen_mode": "all_interfaces", "listener_port": 8080, "running": True}

def test_wait_port_timeout():
    closed = socket.socket(); closed.bind(("127.0.0.1", 0)); closed.close()
    port = closed.getsockname()[1]
    assert wait_port(port, timeout=0.3, poller=lambda p: False) is False

def test_wait_port_open():
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
    port = srv.getsockname()[1]
    try:
        assert wait_port(port, timeout=2) is True
    finally:
        srv.close()

def test_start_idempotent_when_port_open(tmp_path):
    class FakeCfg:  burp_exe = tmp_path / "b.exe"; proxy_port = 8080
    srv = socket.socket(); srv.bind(("127.0.0.1", 8080)); srv.listen(1)
    try:
        assert burp_start(FakeCfg(), tmp_path / "p.burp", tmp_path / "c.json",
                          popen=None) == -1
    finally:
        srv.close()
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
# mph/proxy/burp.py
import json, socket, subprocess, time
from pathlib import Path
from ..errors import HarnessError

def listener_config(port: int) -> dict:
    return {"project_options": {"proxy": {"request_listeners": [
        {"listen_mode": "all_interfaces", "listener_port": port, "running": True}]}}}

def wait_port(port: int, timeout: float = 60, poller=None) -> bool:
    check = poller or (lambda p: _probe(p))
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check(port):
            return True
        time.sleep(1.0)
    return False

def _probe(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", port)) == 0

def burp_start(cfg, project_file: Path, config_file: Path, popen=subprocess.Popen) -> int:
    if _probe(cfg.proxy_port):
        return -1
    if not Path(cfg.burp_exe).exists():
        raise HarnessError(f"burp exe khong ton tai: {cfg.burp_exe}",
                           hint="dat BURP_PATH hoac sua mph.toml [paths]")
    project_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(listener_config(cfg.proxy_port)), encoding="utf-8")
    proc = popen([str(cfg.burp_exe), "--project-file", str(project_file),
                  "--config-file", str(config_file), "--auto-repair"])
    if not wait_port(cfg.proxy_port, timeout=90):
        raise HarnessError("burp khong mo port sau 90s",
                           hint="mo Burp thu cong lan dau de hoan tat wizard license, roi chay lai")
    return proc.pid
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit** — `feat: burp start with listener config and port wait`

---

### Task 6: Burp MCP client (SSE + JSON-RPC)

**Files:**
- Create: `mph/proxy/burp_mcp.py`
- Test: `tests/test_burp_mcp.py`

**Interfaces:**
- Consumes: `Config.burp_mcp_port` (9876).
- Produces: `BurpMcp(port: int).call(tool: str, arguments: dict, timeout: float = 30) -> dict` — trả `result`; raise `HarnessError("burp mcp khong phan hoi", hint=...)` khi không có endpoint event sau 10s. `BurpMcp.tools() -> list[str]`.

- [ ] **Step 1: Failing tests** — stub server chạy thread thật trên port ngẫu nhiên, mô phỏng `/sse` (event `endpoint`) + POST JSON-RPC (`initialize`, `tools/list`, `tools/call`).

```python
# tests/test_burp_mcp.py
import json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import pytest
from mph.proxy.burp_mcp import BurpMcp
from mph.errors import HarnessError

class Stub(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/sse":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(b"event: endpoint\ndata: /mcp?sessionId=abc\n\n")
            self.wfile.flush()
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        resp = {"jsonrpc": "2.0", "id": body.get("id")}
        if body["method"] == "initialize":
            resp["result"] = {"protocolVersion": "2024-11-05"}
        elif body["method"] == "tools/list":
            resp["result"] = {"tools": [{"name": "project_options_get"}]}
        elif body["method"] == "tools/call":
            resp["result"] = {"content": [{"type": "text", "text": "{}"}]}
        self.send_response(202); self.end_headers()
        self.wfile.write(json.dumps(resp).encode())
    def log_message(self, *a): pass

@pytest.fixture()
def stub_server():
    srv = HTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()

def test_call_roundtrip(stub_server):
    mcp = BurpMcp(stub_server)
    r = mcp.call("project_options_get", {})
    assert "result" in r or r == {}

def test_tools_list(stub_server):
    assert "project_options_get" in BurpMcp(stub_server).tools()

def test_no_endpoint_server():
    srv = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)  # không trả SSE
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    try:
        with pytest.raises(HarnessError):
            BurpMcp(port).call("x", {}, timeout=1.0)
    finally:
        srv.shutdown()
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement** — chuyển `Downloads/friendkit_analysis/burp_mcp.py` thành class (giữ nguyên cơ chế SSE + stash).

```python
# mph/proxy/burp_mcp.py
import json, queue, threading, time, urllib.request
from ..errors import HarnessError

class BurpMcp:
    def __init__(self, port: int):
        self.base = f"http://127.0.0.1:{port}"
        self.events: queue.Queue = queue.Queue()
        self._endpoint: str | None = None
        self._id = 0
        threading.Thread(target=self._sse_reader, daemon=True).start()

    def _sse_reader(self) -> None:
        req = urllib.request.Request(self.base + "/sse", headers={"Accept": "text/event-stream"})
        try:
            resp = urllib.request.urlopen(req, timeout=120)
        except OSError:
            return
        ev, data = None, []
        for raw in resp:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
            elif line == "" and (ev or data):
                self.events.put((ev, "\n".join(data)))
                ev, data = None, []

    def _wait_endpoint(self, timeout: float) -> str:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._endpoint:
                return self._endpoint
            try:
                ev, data = self.events.get(timeout=1.0)
            except queue.Empty:
                continue
            if ev == "endpoint":
                self._endpoint = data
                return data
        raise HarnessError("burp mcp khong phan hoi (khong co endpoint event)",
                            hint="bat MCP trong Burp: Settings > Tools/MCP (port 9876) roi chay lai")

    def _call(self, method: str, params: dict | None, timeout: float) -> dict:
        ep = self._wait_endpoint(timeout)
        self._id += 1
        body = {"jsonrpc": "2.0", "method": method, "id": self._id}
        if params is not None:
            body["params"] = params
        req = urllib.request.Request(self.base + ep, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=timeout).read()
        stash = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                ev, data = self.events.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                msg = json.loads(data)
            except ValueError:
                continue
            if msg.get("id") == self._id:
                out = stash
                for s in out:
                    self.events.put(s)
                return msg
            stash.append((ev, data))
        raise HarnessError(f"burp mcp timeout: {method}", hint="kiem tra Burp con chay")

    def call(self, tool: str, arguments: dict, timeout: float = 30.0) -> dict:
        r = self._call("tools/call", {"name": tool, "arguments": arguments}, timeout)
        return r.get("result", r)

    def tools(self) -> list[str]:
        r = self._call("tools/list", None, 30.0)
        return [t.get("name", "") for t in r.get("result", {}).get("tools", [])]
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit** — `feat: burp native mcp client (sse jsonrpc)`

---

### Task 7: CA — fetch, convert, system install

**Files:**
- Create: `mph/proxy/cert.py`
- Test: `tests/test_cert.py` (+ fixture cert tự sinh trong test)

**Interfaces:**
- Consumes: `Config.proxy_port`, `Adb`.
- Produces:
  - `fetch_der(port: int, opener=urllib.request.urlopen) -> bytes`
  - `pem_and_name(der: bytes) -> tuple[str, str]` — PEM + `<subject_hash_old>.0` (MD5 4-byte little-endian của DER subject, hex 8 ký tự).
  - `install_system_ca(der: bytes, adb: Adb) -> str` — `root` → `remount` → push `/system/etc/security/cacerts/<name>.0` → chmod 644; trả tên file; idempotent (ghi đè).

- [ ] **Step 1: Failing tests**

```python
# tests/test_cert.py
import struct, hashlib
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
import datetime
from mph.proxy.cert import pem_and_name, fetch_der, install_system_ca

def _self_signed() -> bytes:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "portswigger-cnet")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256()))
    return cert.public_bytes(serialization.Encoding.DER)

def test_pem_and_name_format():
    der = _self_signed()
    pem, name = pem_and_name(der)
    assert pem.startswith("-----BEGIN CERTIFICATE-----")
    assert len(name) == 10 and name.endswith(".0") and name[:8].lower() == name[:8]
    cert = x509.load_der_x509_certificate(der)
    expect = struct.unpack("<I", hashlib.md5(
        cert.subject.public_bytes()).digest()[:4])[0]
    assert name == f"{expect:08x}.0"

def test_fetch_der(monkeypatch):
    der = _self_signed()
    monkeypatch.setattr("mph.proxy.cert.urllib.request.urlopen",
                        lambda url, timeout=None: type("R", (), {"read": lambda s: der})())
    assert fetch_der(8080) == der

class FakeAdb:
    def __init__(self): self.calls = []
    def run(self, *args, timeout=60, device=True):
        self.calls.append(args)
        return type("R", (), {"ok": True, "out": "", "err": "", "code": 0})()

def test_install_overwrites():
    der = _self_signed()
    a = FakeAdb()
    n1 = install_system_ca(der, a)
    n2 = install_system_ca(der, a)
    assert n1 == n2 and len(a.calls) >= 8  # 2 lần × (root+remount+push+chmod)
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
# mph/proxy/cert.py
import hashlib, struct, tempfile, urllib.request
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from ..errors import HarnessError

def fetch_der(port: int, opener=urllib.request.urlopen) -> bytes:
    try:
        with opener(f"http://127.0.0.1:{port}/cert", timeout=10) as r:
            return r.read()
    except OSError as e:
        raise HarnessError(f"khong tai duoc CA tu :{port}/cert — Burp chay chua?",
                           hint=str(e)) from e

def pem_and_name(der: bytes) -> tuple[str, str]:
    cert = x509.load_der_x509_certificate(der)
    pem = cert.public_bytes(serialization.Encoding.PEM).decode("ascii")
    h = hashlib.md5(cert.subject.public_bytes()).digest()[:4]
    name = f"{struct.unpack('<I', h)[0]:08x}.0"
    return pem, name

def install_system_ca(der: bytes, adb) -> str:
    pem, name = pem_and_name(der)
    for args, hint in ((("root",), "image google_apis moi cho phep adb root"),
                       (("remount",), "thu: adb disable-verity && adb reboot && remount")):
        r = adb.run(*args, timeout=60, device=False)
        if not r.ok:
            raise HarnessError(f"adb {args[0]} that bai", hint=hint)
    with tempfile.NamedTemporaryFile("w", suffix=".0", delete=False, encoding="ascii") as f:
        f.write(pem)
        local = Path(f.name)
    remote = f"/system/etc/security/cacerts/{name}"
    push = adb.run("push", str(local), remote, timeout=60, device=False)
    if not push.ok:
        raise HarnessError("push CA that bai", hint=push.err)
    adb.run("shell", "chmod", "644", remote)
    return name
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit** — `feat: burp CA fetch + system-store install`

---

### Task 8: Proxy routing on/off

**Files:**
- Create: `mph/proxy/route.py`
- Test: `tests/test_route.py`

**Interfaces:**
- Consumes: `Adb`, `Config.proxy_port`.
- Produces: `proxy_on(adb: Adb, port: int) -> None` (`adb reverse tcp:<port> tcp:<port>` + `settings put global http_proxy 127.0.0.1:<port>`); `proxy_off(adb: Adb) -> None` (http_proxy `:0`, `adb reverse --remove-all`). Cả hai qua shell device (có serial).

- [ ] **Step 1: Failing tests**

```python
# tests/test_route.py
from mph.proxy.route import proxy_on, proxy_off

class FakeAdb:
    def __init__(self): self.calls = []
    def run(self, *args, timeout=60, device=True):
        self.calls.append(args)
        return type("R", (), {"ok": True, "out": "", "err": "", "code": 0})()

def test_proxy_on_sets_reverse_and_global():
    a = FakeAdb(); proxy_on(a, 8080)
    assert ("reverse", "tcp:8080", "tcp:8080") in a.calls
    assert any("http_proxy" in " ".join(c) and "127.0.0.1:8080" in " ".join(c) for c in a.calls)

def test_proxy_off_cleans():
    a = FakeAdb(); proxy_off(a)
    assert ("reverse", "--remove-all") in a.calls
    assert any("http_proxy" in " ".join(c) and ":0" in " ".join(c) for c in a.calls)
```

- [ ] **Step 2: Run — expect FAIL** → **Step 3:**

```python
# mph/proxy/route.py
from ..errors import HarnessError

def proxy_on(adb, port: int) -> None:
    r = adb.run("reverse", f"tcp:{port}", f"tcp:{port}")
    if not r.ok:
        raise HarnessError("adb reverse that bai", hint=r.err)
    adb.run("shell", "settings", "put", "global", "http_proxy", f"127.0.0.1:{port}")

def proxy_off(adb) -> None:
    adb.run("shell", "settings", "put", "global", "http_proxy", ":0")
    adb.run("reverse", "--remove-all")
```

- [ ] **Step 4: PASS** → **Step 5: Commit** — `feat: proxy routing on/off`

---

### Task 9: Wire CLI (setup, proxy, burp, cert groups)

**Files:**
- Modify: `mph/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: mọi module trên.
- Produces: lệnh `mph setup` (bootstrap → tạo AVD → boot → wait_booted → adb root), `mph burp start|status`, `mph proxy on|off`, `mph cert install`, `mph device status`. Các command nhận dependency injection qua module-level factory `mph.cli._build()` trả `(cfg, adb_factory)` để test monkeypatch.

- [ ] **Step 1: Failing tests**

```python
# tests/test_cli.py
from typer.testing import CliRunner
import mph.cli as cli_mod
from mph.cli import app

runner = CliRunner()

def test_help_lists_groups():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0 and "setup" in r.output and "burp" in r.output

def test_burp_status_no_burp(tmp_path, monkeypatch):
    class FakeCfg:
        burp_exe = tmp_path / "nope.exe"; proxy_port = 8080; burp_mcp_port = 9876
    monkeypatch.setattr(cli_mod, "_load_config", lambda: FakeCfg())
    r = runner.invoke(app, ["burp", "status"])
    assert r.exit_code == 0 and "not running" in r.output
```

- [ ] **Step 2: FAIL** → **Step 3: Implement** — thêm groups:

```python
# mph/cli.py (bổ sung)
import json as _json
from pathlib import Path
from .bootstrap import ensure_cmdline_tools, install_image, create_avd
from .device import avd as avd_mod
from .device.adb import Adb
from .proxy import burp as burp_mod, route as route_mod, cert as cert_mod

def _load_config():
    return load_config()

setup_app = typer.Typer(); burp_app = typer.Typer(); proxy_app = typer.Typer()
app.add_typer(setup_app, name="setup"); app.add_typer(burp_app, name="burp")
app.add_typer(proxy_app, name="proxy")

@setup_app.command("run")
def setup_run() -> None:
    """Bootstrap SDK + AVD + boot + adb root (idempotent)."""
    cfg = _load_config()
    tools = Path(cfg.sdk) / "cmdline-tools" / "latest"
    if not (tools / "bin" / "sdkmanager.bat").exists():
        ensure_cmdline_tools(Path(cfg.sdk), Path("tools") / "cache")
    install_image(Path(cfg.sdk), cfg.image)
    create_avd(Path(cfg.sdk), cfg.avd_name, cfg.image)
    avd_mod.avd_boot(Path(cfg.sdk), cfg.avd_name)
    serial = avd_mod.avd_serial()
    if not serial:
        raise typer.Exit("khong thay emulator serial sau boot", code=1)
    adb = Adb(serial=serial)
    if not avd_mod.wait_booted(serial, adb):
        raise typer.Exit("timeout cho boot (300s)", code=1)
    adb.run("root"); print(f"ready: {serial}")

@burp_app.command("start")
def burp_start_cmd() -> None:
    cfg = _load_config()
    pf = cfg.workspace / "_shared" / "burp" / "main.burp"
    pid = burp_mod.burp_start(cfg, pf, pf.with_suffix(".json"))
    print("burp running" if pid == -1 else f"burp pid={pid}")

@burp_app.command("status")
def burp_status_cmd() -> None:
    cfg = _load_config()
    import socket
    up = socket.socket().connect_ex(("127.0.0.1", cfg.proxy_port)) == 0
    print("running" if up else "not running")
    raise typer.Exit(code=0 if up else 1)

@proxy_app.command("on")
def proxy_on_cmd() -> None:
    cfg = _load_config(); serial = avd_mod.avd_serial()
    adb = Adb(serial=serial) if serial else Adb()
    route_mod.proxy_on(adb, cfg.proxy_port); print("proxy on")

@proxy_app.command("off")
def proxy_off_cmd() -> None:
    serial = avd_mod.avd_serial()
    adb = Adb(serial=serial) if serial else Adb()
    route_mod.proxy_off(adb); print("proxy off")

@app.command()
def cert(serial: str | None = None) -> None:
    """Tai CA Burp va cai vao system store cua device."""
    cfg = _load_config()
    der = cert_mod.fetch_der(cfg.proxy_port)
    name = cert_mod.install_system_ca(der, Adb(serial=serial) if serial else Adb())
    print(f"installed {name}")
```

(chỉnh `burp status` test mapping cho khớp chữ in ra — dùng `print("not running")`.)

- [ ] **Step 4: Run** `python -m pytest tests/test_cli.py -v` — PASS.

- [ ] **Step 5: Commit** — `feat: cli groups setup/burp/proxy/cert`

---

### Task 10: `mph selftest --phase p1` — integration orchestrator

**Files:**
- Create: `mph/selftest.py`
- Modify: `mph/cli.py` (thêm command `selftest`)
- Test: `tests/test_selftest.py`

**Interfaces:**
- Consumes: toàn bộ tasks trên + `Adb`.
- Produces: `run_p1(cfg, deps=None) -> tuple[bool, list[tuple[str, bool, str]]]` — deps injectable (mặc định thật) gồm: `avd_serial, wait_booted, adb_root, burp_start, fetch_der, install_system_ca, proxy_on, device_https_probe`. Bước cuối `device_https_probe`: `adb shell curl -sx http://127.0.0.1:8080 -o /dev/null -w %{http_code} https://example.com` → "200". Nếu device thiếu curl → probe trả ("nocurl", hint cài curl module / dùng ảnh API 34 có sẵn).

- [ ] **Step 1: Failing tests**

```python
# tests/test_selftest.py
from mph.selftest import run_p1

class Deps:  # fake toàn bộ, chỉ https fail
    avd_serial = staticmethod(lambda: "emulator-5554")
    wait_booted = staticmethod(lambda *a, **k: True)
    adb_root = staticmethod(lambda adb: adb)
    burp_start = staticmethod(lambda *a, **k: 123)
    fetch_der = staticmethod(lambda port: b"\x30\x03\x02\x01\x01")
    install_system_ca = staticmethod(lambda der, adb: "a1b2c3d4.0")
    proxy_on = staticmethod(lambda adb, port: None)
    @staticmethod
    def device_https_probe(adb, port):
        return "000", "connection refused"
    @staticmethod
    def adb_factory(serial): return object()

def test_p1_fails_at_https_with_diagnosis():
    ok, rows = run_p1(None, deps=Deps)
    assert ok is False
    last = rows[-1]
    assert last[0].startswith("https-probe") and last[1] is False
    assert "000" in last[2] or "refused" in last[2]

def test_p1_all_green():
    class DepsOK(Deps):
        @staticmethod
        def device_https_probe(adb, port):
            return "200", ""
    ok, rows = run_p1(None, deps=DepsOK)
    assert ok is True and len(rows) >= 6
```

- [ ] **Step 2: FAIL** → **Step 3:**

```python
# mph/selftest.py
from dataclasses import dataclass
from .device import avd as avd_mod
from .device.adb import Adb
from .proxy import burp as burp_mod, cert as cert_mod, route as route_mod

def _device_https_probe(adb: Adb, port: int) -> tuple[str, str]:
    have = adb.run("shell", "command -v curl")
    if not have.ok or "curl" not in have.out:
        return "nocurl", "device thieu curl — dung image google_apis API 34 hoac push curl"
    r = adb.run("shell", f"curl -sx http://127.0.0.1:{port} -o /dev/null -w %{{http_code}} https://example.com",
                timeout=60)
    return r.out.strip() or "000", r.err.strip()

def _adb_root(adb: Adb) -> Adb:
    adb.run("root")
    return adb

@dataclass(frozen=True)
class Deps:
    avd_serial = staticmethod(avd_mod.avd_serial)
    wait_booted = staticmethod(avd_mod.wait_booted)
    adb_root = staticmethod(_adb_root)
    adb_factory = staticmethod(lambda serial: Adb(serial=serial))
    burp_start = staticmethod(burp_mod.burp_start)
    fetch_der = staticmethod(cert_mod.fetch_der)
    install_system_ca = staticmethod(cert_mod.install_system_ca)
    proxy_on = staticmethod(route_mod.proxy_on)
    device_https_probe = staticmethod(_device_https_probe)

def run_p1(cfg, deps: Deps | None = None) -> tuple[bool, list[tuple[str, bool, str]]]:
    d = deps or Deps()
    rows: list[tuple[str, bool, str]] = []
    def step(name, fn, *a):
        try:
            detail = fn(*a) or "ok"
            rows.append((name, True, str(detail)))
            return True
        except Exception as e:  # noqa: BLE001 — selftest tổng hợp mọi lỗi
            rows.append((name, False, str(e)))
            return False
    serial = d.avd_serial()
    if not serial or not step("boot", d.wait_booted, serial, d.adb_factory(serial)):
        return False, rows
    adb = d.adb_root(d.adb_factory(serial))
    if not step("burp", d.burp_start, cfg, cfg.workspace / "_shared/burp/main.burp",
                cfg.workspace / "_shared/burp/main.json"):
        return False, rows
    der = d.fetch_der(cfg.proxy_port)
    step("ca", d.install_system_ca, der, adb)
    step("proxy-on", d.proxy_on, adb, cfg.proxy_port)
    code, err = d.device_https_probe(adb, cfg.proxy_port)
    ok = code == "200"
    rows.append(("https-probe", ok, f"code={code} {err}"))
    return ok, rows
```

CLI thêm:

```python
@app.command()
def selftest(phase: str = typer.Option("p1")) -> None:
    """Chay kiem tra tich hop; p1 = den HTTPS qua Burp tu device."""
    from .selftest import run_p1
    cfg = _load_config()
    ok, rows = run_p1(cfg)
    for name, good, detail in rows:
        print(f"[{'OK ' if good else 'FAIL'}] {name}: {detail}")
    raise typer.Exit(code=0 if ok else 1)
```

- [ ] **Step 4: Unit PASS** (`python -m pytest tests/test_selftest.py -v`)

- [ ] **Step 5: Integration thật (cổng DoD P1)** — chạy tuần tự, từng bước sửa tới xanh:
  1. `python -c "from mph.cli import app; app()" setup run` (bootstrap+AVD ~10 phút lần đầu)
  2. `python -c "from mph.cli import app; app()" burp start`
  3. `python -c "from mph.cli import app; app()" selftest --phase p1`
  Expected cuối: `[OK] https-probe: code=200`. Ghi log vào `workspace/logs/`.

- [ ] **Step 6: Commit** — `feat: selftest p1 end-to-end (setup->burp->ca->https 200)`

---

## Tổng quan các phase kế tiếp (mỗi phase một plan riêng, cùng thư mục này)

- **P2 plan** — RootAVD/Magisk + DenyList + Shamiko + PIF (stack integrity 5 lớp §4.3), vendored BrutDroid pin SHA + wrapper scripted-stdin (đường thay thế), StrongR-frida + hide + `scripts/frida/unpin.js`, `mph integrity check`, selftest mở rộng.
- **P3 plan** — `re/`: apks pull, jadx decompile, manifest recon, codebase-memory index (gọi MCP qua config registry), jadx-mcp-server.
- **P4 plan** — `mcp_server/server.py` (FastMCP) + `device/screen.py` (screencap+wm-size mapping+tap/swipe/text+uiautomator) + skills `mp-*`.
- **P5 plan** — Audit Quality Engine: prompts 4-pass, finder/verifier, coverage manifest, `mph bench` (OVAA, InsecureBankv2, DVHMA, UnCrackable L1–L4, Allsafe).
- **P6 plan** — Runner `run.ps1` + `mph run --mode ai|manual`, agent engine opencode/deepseek-v4.1-flash full-perm effort-max (+ engine claude/none), state.json resume, `docs/playbook.md`, notify.
