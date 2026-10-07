# tests/test_avd.py
from mph.device.avd import wait_serial

def test_wait_serial_finds_emulator():
    calls = []
    def devices():
        calls.append(1)
        return [("a35d6a420508", "device"), ("emulator-5554", "device")] if len(calls) > 1 else []
    s = wait_serial(timeout=5, devices=devices, sleeper=lambda _: None)
    assert s == "emulator-5554" and len(calls) == 2

def test_wait_serial_timeout():
    s = wait_serial(timeout=0.1, devices=lambda: [], sleeper=lambda _: None)
    assert s is None
