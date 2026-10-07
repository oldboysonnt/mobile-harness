# tests/test_route.py
from mph.proxy.route import proxy_on, proxy_off

class FakeAdb:
    def __init__(self): self.calls = []
    def su(self, cmd, timeout=60):
        return self.run("shell", f"su -c {cmd}", timeout=timeout)

    def run(self, *args, timeout=60, device=True):
        self.calls.append(args)
        return type("R", (), {"ok": True, "out": "", "err": "", "code": 0})()

def test_proxy_on_sets_reverse_and_global():
    a = FakeAdb(); proxy_on(a, 8080)
    assert ("reverse", "--remove tcp:8080") in a.calls  # re-add đề phòng rule chết
    assert ("reverse", "tcp:8080", "tcp:8080") in a.calls
    assert any("http_proxy" in " ".join(c) and "127.0.0.1:8080" in " ".join(c) for c in a.calls)

def test_proxy_off_cleans():
    a = FakeAdb(); proxy_off(a)
    assert ("reverse", "--remove-all") in a.calls
    assert any("http_proxy" in " ".join(c) and ":0" in " ".join(c) for c in a.calls)
