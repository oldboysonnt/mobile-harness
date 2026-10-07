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
    calls, runner = _fake_run([(1, "", "device offline")] * 4)
    a = Adb(serial="e", runner=runner, sleeper=lambda s: None)
    r = a.run("shell", "true")
    assert not r.ok and len(calls) == 4  # 1 lần đầu + 3 retry (backoff 0.5/1/2)

def test_backoff_sequence():
    sleeps = []
    calls, runner = _fake_run([(1, "", "device offline")] * 4)
    a = Adb(serial="e", runner=runner, sleeper=sleeps.append)
    a.run("shell", "true")
    assert sleeps == [0.5, 1.0, 2.0]

def test_timeout_expired_retried_not_raised():
    import subprocess
    calls = []
    def runner(cmd, timeout=None):
        calls.append(cmd)
        if len(calls) < 2:
            raise subprocess.TimeoutExpired(cmd, timeout)
        return (0, "ok", "")
    a = Adb(serial="e", runner=runner, sleeper=lambda s: None)
    r = a.run("shell", "true")
    assert r.ok and len(calls) == 2

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
