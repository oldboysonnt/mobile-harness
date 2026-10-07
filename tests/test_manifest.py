# tests/test_manifest.py
from pathlib import Path

import pytest

from mph.errors import HarnessError
from mph.re.manifest import parse_manifest

MANIFEST = """<?xml version="1.0"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.example.app">
  <uses-permission android:name="android.permission.INTERNET"/>
  <uses-permission android:name="android.permission.CAMERA"/>
  <application android:debuggable="true" android:allowBackup="true">
    <activity android:name=".Main" android:exported="true"/>
    <activity android:name=".Hidden"/>
    <activity android:name=".Deep">
      <intent-filter>
        <action android:name="android.intent.action.VIEW"/>
        <data android:scheme="myapp" android:host="pay"/>
      </intent-filter>
    </activity>
    <service android:name=".Svc" android:exported="true"/>
    <receiver android:name=".Rcv"/>
    <provider android:name=".Pvd" android:authorities="com.example.pvd"/>
  </application>
</manifest>
"""

def _mk(tmp):
    out = tmp / "jadx-out" / "resources"
    out.mkdir(parents=True)
    (out / "AndroidManifest.xml").write_text(MANIFEST, encoding="utf-8")
    return tmp / "jadx-out"

def test_parse_manifest_fields(tmp_path):
    m = parse_manifest(_mk(tmp_path))
    assert m["package"] == "com.example.app"
    assert m["debuggable"] is True and m["allowBackup"] is True
    assert "android.permission.INTERNET" in m["permissions"]
    assert ".Main" in m["exported"]["activities"]
    assert ".Hidden" not in m["exported"]["activities"]
    assert ".Svc" in m["exported"]["services"]
    dl = m["deeplinks"][0]
    assert dl["component"] == ".Deep" and "myapp" in dl["schemes"]

def test_manifest_missing_raises(tmp_path):
    out = tmp_path / "jadx-out"
    out.mkdir()
    with pytest.raises(HarnessError) as e:
        parse_manifest(out)
    assert "AndroidManifest.xml" in str(e.value)

def test_manifest_malformed_raises(tmp_path):
    out = tmp_path / "jadx-out" / "resources"
    out.mkdir(parents=True)
    (out / "AndroidManifest.xml").write_text("<manifest><broken", encoding="utf-8")
    with pytest.raises(HarnessError):
        parse_manifest(out.parent)
