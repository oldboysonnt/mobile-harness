# tests/test_brutdroid.py
from mph.root.brutdroid import brutdroid_vendor

def test_vendor_clones_once(tmp_path):
    calls = []

    def runner(cmd, timeout=None):
        calls.append(cmd)
        return type("R", (), {"returncode": 0})()

    class FakeRevParse:
        returncode = 0
        stdout = "abc123\n"

    import mph.root.brutdroid as B
    orig = B._rev_parse
    B._rev_parse = lambda d: FakeRevParse()
    try:
        d = brutdroid_vendor(tmp_path / "BrutDroid", runner=runner)
        brutdroid_vendor(tmp_path / "BrutDroid", runner=runner)
    finally:
        B._rev_parse = orig
    assert len(calls) == 1
    assert (tmp_path / "BrutDroid" / "BRUTDROID.sha").read_text() == "abc123"
    assert d == tmp_path / "BrutDroid"
