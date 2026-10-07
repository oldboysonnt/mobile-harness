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
