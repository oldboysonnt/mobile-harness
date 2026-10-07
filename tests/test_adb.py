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
