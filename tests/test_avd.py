# tests/test_avd.py
from mph.device.avd import wait_serial, avd_serial

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

def test_avd_serial_matches_by_name():
    name_of = {"emulator-5554": "mph_avd", "emulator-5562": "Pixel_6_Pro"}
    devs = [("emulator-5554", "device"), ("emulator-5562", "device")]
    assert avd_serial("mph_avd", devices=lambda: devs,
                      name_of=lambda s: name_of[s]) == "emulator-5554"

def test_avd_serial_skips_offline():
    name_of = {"emulator-5562": "mph_avd"}
    devs = [("emulator-5554", "offline"), ("emulator-5562", "device")]
    assert avd_serial("mph_avd", devices=lambda: devs,
                      name_of=lambda s: name_of.get(s)) == "emulator-5562"

def test_avd_serial_ambiguous_unknown_names_returns_none():
    devs = [("emulator-5554", "device"), ("emulator-5562", "device")]
    assert avd_serial("mph_avd", devices=lambda: devs,
                      name_of=lambda s: None) is None

def test_avd_serial_single_unknown_accepted():
    assert avd_serial("mph_avd", devices=lambda: [("emulator-5554", "device")],
                      name_of=lambda s: None) == "emulator-5554"
