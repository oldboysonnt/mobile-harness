# tests/test_screen.py
import pytest

from mph.device.screen import key, swipe, tap, type_text, wm_size

class FakeAdb:
    def __init__(self, out="Physical size: 1080x2400\n"):
        self.out = out
        self.calls = []

    def run(self, *args, timeout=60, device=True):
        self.calls.append(" ".join(args))
        return type("R", (), {"ok": True, "out": self.out, "err": "",
                              "code": 0})()

def test_wm_size_basic():
    assert wm_size(FakeAdb()) == (1080, 2400)

def test_wm_size_prefers_override():
    a = FakeAdb("Physical size: 1080x2400\nOverride size: 720x1600\n")
    assert wm_size(a) == (720, 1600)

def test_tap_and_key():
    a = FakeAdb()
    tap(a, 540, 1200)
    key(a, "3")
    assert any("input tap 540 1200" in c for c in a.calls)
    assert any("input keyevent 3" in c for c in a.calls)

def test_swipe():
    a = FakeAdb()
    swipe(a, 100, 200, 300, 400, 250)
    assert any("input swipe 100 200 300 400 250" in c for c in a.calls)

def test_type_text_escapes():
    a = FakeAdb()
    type_text(a, "hello world")
    assert any("hello%sworld" in c for c in a.calls)

def test_type_text_rejects_control():
    with pytest.raises(Exception):
        type_text(FakeAdb(), "bad\nnewline")

def test_screenshot_writes_png(tmp_path, monkeypatch):
    import mph.device.screen as S
    png = b"\x89PNG\r\n\x1a\n" + b"FAKEDATA" * 10
    monkeypatch.setattr(S, "_screencap_raw", lambda adb: (0, png))
    dest = tmp_path / "s.png"
    meta = S.screenshot(FakeAdb(), dest)
    assert dest.read_bytes()[:4] == b"\x89PNG"
    assert meta["path"] == str(dest) and meta["screen"] == [1080, 2400]

def test_screenshot_rejects_corrupt(tmp_path, monkeypatch):
    import mph.device.screen as S
    monkeypatch.setattr(S, "_screencap_raw", lambda adb: (0, b"NOTPNG!!"))
    from mph.errors import HarnessError
    with pytest.raises(HarnessError):
        S.screenshot(FakeAdb(), tmp_path / "s.png")

def test_find_bounds_center(tmp_path):
    import mph.device.screen as S
    xml = tmp_path / "ui.xml"
    xml.write_text(
        '<hierarchy><node bounds="[100,200][300,400]" text="OK"/></hierarchy>',
        encoding="utf-8")
    assert S.find_bounds(xml, "OK") == (200, 300)
    assert S.find_bounds(xml, "NOPE") is None
