# tests/test_spic.py
from mph.root.spic import parse_verdict

def test_parse_basic():
    xml = '<node text="MEETS_BASIC_INTEGRITY"/><node text="anything"/>'
    assert parse_verdict(xml) == "MEETS_BASIC"

def test_parse_device_priority():
    xml = '<node text="MEETS_BASIC"/><node text="MEETS_DEVICE_INTEGRITY"/>'
    assert parse_verdict(xml) == "MEETS_DEVICE"

def test_parse_none():
    xml = '<node text="hello"/>'
    assert parse_verdict(xml) == "NO_VERDICT"

def test_launch_fail_raises():
    import pytest as _p
    from mph.errors import HarnessError as HE
    from mph.root import spic as S

    class A:
        def run(self, *args, timeout=60, device=True):
            if args[1:3] == ("am", "start"):
                return type("R", (), {"ok": False, "out": "Activity class does not exist",
                                      "err": "", "code": 1})()
            return type("R", (), {"ok": True, "out": "package:com.henrikherzig.playintegritychecker",
                                  "err": "", "code": 0})()

    class C:
        tools_dir = "nope"
    with _p.raises(HE) as e:
        S.integrity_check(A(), C(), __import__("pathlib").Path("x"))
    assert "SPIC launch" in str(e.value)
