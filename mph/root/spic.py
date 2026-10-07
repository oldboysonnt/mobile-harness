"""Đo Play Integrity verdict thật bằng app SPIC + uiautomator."""
import time
from pathlib import Path

from ..device import screen
from ..errors import HarnessError

_LEVELS = ["MEETS_STRONG_INTEGRITY", "MEETS_DEVICE", "MEETS_BASIC"]
_PKG = "com.henrikherzig.playintegritychecker"  # SPIC (herzhenr/spic-android)
_ACTIVITY = f"{_PKG}/MainActivity"  # integration sửa nếu launchable khác


def parse_verdict(ui_xml_text: str) -> str:
    """Trả mức CAO NHẤT tìm được trong dump; NO_VERDICT nếu không có."""
    best = None
    for lv in _LEVELS:
        if lv in ui_xml_text:
            best = lv
            break
    if best is None and "NO_INTEGRITY" in ui_xml_text:
        return "NO_INTEGRITY"
    return best or "NO_VERDICT"


def integrity_check(adb, cfg, ws: Path) -> dict:
    """Install (nếu thiếu) + mở SPIC + poll verdict; evidence screenshot."""
    have = adb.run("shell", "pm", "list", "packages")
    if _PKG not in (have.out or ""):
        apk = Path(cfg.tools_dir) / "spic.apk"
        if not apk.exists():
            raise HarnessError("thieu tools/spic.apk", hint="chay mph bootstrap")
        r = adb.run("install", "-r", str(apk), timeout=120)
        if not r.ok:
            raise HarnessError("cai SPIC that bai", hint=(r.out or "")[-200:])
    adb.run("shell", "am", "force-stop", _PKG)
    adb.run("shell", "am", "start", "-n", _ACTIVITY)
    ws = Path(ws)
    ws.mkdir(parents=True, exist_ok=True)
    verdict = "NO_VERDICT"
    dump = ws / "spic_ui.xml"
    for _ in range(6):
        time.sleep(3)
        try:
            screen.ui_dump(adb, dump)
            verdict = parse_verdict(dump.read_text(encoding="utf-8",
                                                   errors="replace"))
        except HarnessError:
            continue
        if verdict != "NO_VERDICT":
            break
    shot = ws / "spic_evidence.png"
    try:
        screen.screenshot(adb, shot)
    except HarnessError:
        shot = None
    # SPIC là app Compose — uiautomator không đọc text; verdict trong PIXELS:
    # trả SEE_SCREENSHOT + evidence để AI/người đọc (MEETS_BASIC đã xác nhận
    # bằng mắt 2026-10-08 trên stack PIF này).
    if verdict == "NO_VERDICT" and shot is not None:
        verdict = "SEE_SCREENSHOT"
    return {"verdict": verdict, "evidence": str(shot) if shot else ""}
