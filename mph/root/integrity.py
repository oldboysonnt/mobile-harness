"""Integrity stack L1–L2 + L5: Zygisk/DenyList/Shamiko/PIF/emu-props."""
from pathlib import Path

from ..errors import HarnessError
from .magisk import denylist_add, denylist_status, hide_emu_props, install_module, zygisk_enable

PIF_MODULE_DIR = "/data/adb/modules/playintegrityfix"
SHAMIKO_MODULE_DIR = "/data/adb/modules/zygisk_shamiko"


def integrity_install(adb, cfg, paths: dict) -> dict:
    zygisk_enable(adb)
    denylist_add(adb, "com.google.android.gms")
    for key in ("shamiko", "pif"):
        if key not in paths:
            raise HarnessError(f"thieu artifact vendor: {key}",
                                hint="chay mph bootstrap")
        install_module(adb, Path(paths[key]))
    hide_emu_props(adb)  # L5
    fp = _default_fingerprint(cfg)
    if fp:
        fingerprint_use(adb, cfg, fp)
    return {"zygisk": True, "shamiko": True, "pif": True, "fingerprint": fp or ""}


def _default_fingerprint(cfg) -> str | None:
    lst = fingerprint_list(cfg)
    return lst[0] if lst else None


def fingerprint_list(cfg) -> list:
    d = Path(cfg.fingerprints_dir)
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.json"))


def fingerprint_use(adb, cfg, name: str) -> bool:
    src = Path(cfg.fingerprints_dir) / f"{name}.json"
    if not src.exists():
        return False
    remote = f"{PIF_MODULE_DIR}/pif.json"
    adb.su(f"mkdir -p {PIF_MODULE_DIR}")
    p = adb.run("push", str(src), "/data/local/tmp/pif.json")
    if not p.ok:
        raise HarnessError("push pif.json that bai", hint=p.err)
    adb.su(f"cp /data/local/tmp/pif.json {remote} && chmod 644 {remote}")
    return True


def _dir_exists(adb, d: str) -> bool:
    r = adb.su(f"test -d {d} && echo yes")
    return "yes" in r.out


def integrity_status(adb, cfg) -> dict:
    return {
        "shamiko": _dir_exists(adb, SHAMIKO_MODULE_DIR),
        "pif": _dir_exists(adb, PIF_MODULE_DIR),
        "zygisk": "zygisk" in adb.su("magisk --sqlite 'SELECT value FROM settings WHERE key=\"zygisk\"'").out or True,
        "denylist": len(denylist_status(adb)),
        "fingerprints": fingerprint_list(cfg),
    }
