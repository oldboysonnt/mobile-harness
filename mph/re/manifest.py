"""Phân tích AndroidManifest (từ jadx-out) thành attack surface."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from ..errors import HarnessError

_NS = "{http://schemas.android.com/apk/res/android}"
_COMP = {"activity": "activities", "service": "services",
         "receiver": "receivers", "provider": "providers",
         "activity-alias": "aliases"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _attr(el, name: str):
    return el.get(_NS + name)


def parse_manifest(jadx_out: Path) -> dict:
    """Trả dict: package/flags/permissions/exported components/deeplinks."""
    f = Path(jadx_out) / "resources" / "AndroidManifest.xml"
    if not f.exists():
        raise HarnessError("khong thay AndroidManifest.xml", hint=str(f))
    raw = f.read_text(encoding="utf-8", errors="replace")
    # hardening XXE/billion-laughs (input là APK third-party = untrusted):
    # manifest do jadx render không bao giờ có DTD/ENTITY → gặp là từ chối
    if "<!DOCTYPE" in raw or "<!ENTITY" in raw:
        raise HarnessError("manifest chua DTD/ENTITY — tu choi vi bao mat",
                            hint=str(f))
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise HarnessError(f"manifest khong parse duoc: {f.name}",
                            hint=str(e)) from e
    app = root.find("application")
    exported = {"activities": [], "services": [], "receivers": [],
                "providers": [], "aliases": []}
    deeplinks = []
    alias_targets: dict = {}
    provider_authorities: dict = {}
    if app is not None:
        for el in app:
            kind = _local(el.tag)
            if kind not in _COMP:
                continue
            name = _attr(el, "name") or ""
            if kind == "activity-alias":
                tgt = _attr(el, "targetActivity")
                if tgt:
                    alias_targets[name] = tgt
            if kind == "provider":
                auth = _attr(el, "authorities")
                if auth:
                    provider_authorities[name] = auth
            exp = _attr(el, "exported")
            has_filter = el.find("intent-filter") is not None
            if exp == "true" or (exp is None and has_filter):
                exported[_COMP[kind]].append(name)
            for flt in el.findall("intent-filter"):
                schemes, hosts, mimes = [], [], []
                for data in flt.findall("data"):
                    for attr, bucket in (("scheme", schemes), ("host", hosts),
                                         ("mimeType", mimes)):
                        v = _attr(data, attr)
                        if v:
                            bucket.append(v)
                if schemes:
                    deeplinks.append({"component": name, "schemes": schemes,
                                      "hosts": hosts, "mimeTypes": mimes})
    return {
        "package": root.get("package", ""),
        "debuggable": (_attr(app, "debuggable") == "true"
                       if app is not None else False),
        "allowBackup": (_attr(app, "allowBackup") != "false"
                        if app is not None else True),
        "permissions": [p.get(_NS + "name", "") for p in
                        root.findall("uses-permission")
                        + root.findall("uses-permission-sdk-23")],
        "exported": exported,
        "alias_targets": alias_targets,
        "provider_authorities": provider_authorities,
        "deeplinks": deeplinks,
    }


def write_summary(manifest: dict, dest: Path) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    return dest
