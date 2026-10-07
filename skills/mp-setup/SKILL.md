---
name: mp-setup
description: Dựng/kiểm tra môi trường pentest mobile (emulator root, frida, Burp proxy) — dùng khi chuẩn bị hoặc kiểm tra thiết bị trước audit.
---

# mp-setup

Chạy tuần tự (cwd = repo mobile-harness):

1. `mph doctor` — mọi hàng phải OK.
2. `mph setup run` — bootstrap + AVD + adb root (idempotent).
3. `mph root install` — Magisk + integrity stack (cần emulator TẮT trước).
4. `mph frida start` — frida-server ẩn.
5. `mph burp start` + `mph proxy on` + `mph cert` — traffic qua Burp 8082.
6. `mph selftest --phase p2` — xanh là môi trường sẵn sàng.

Điều khiển màn hình qua MCP `mph` (mph_screenshot → nhìn ảnh → mph_tap theo
tọa độ thật trong meta `screen`). Spec: docs/superpowers/specs/2026-10-07-mobile-pentest-harness-design.md
