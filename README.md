# mph — Mobile Pentest Harness

AI harness cho mobile pentesting (Android): tự động setup emulator root +
bypass (root/SSL/Play Integrity), route traffic qua Burp Suite, decompile &
index mã nguồn (jadx → codebase-memory-mcp), điều khiển màn hình theo tọa độ,
và chạy AI agent (opencode/deepseek) audit + pentest tự động.

## Ràng buộc sử dụng

Harness này **chỉ dùng để phân tích ứng dụng được ủy quyền**: app tự phát triển,
chương trình bug bounty còn scope, CTF/lab, hoặc có hợp đồng kiểm thử.
(Xem spec §1 — `docs/superpowers/specs/2026-10-07-mobile-pentest-harness-design.md`.)

## Bắt đầu nhanh — 1 click (pentest thủ công, không AI)

```powershell
# chuột phải setup-manual.ps1 > Run with PowerShell, hoặc double-click:
.\setup-manual.cmd
# kèm app đích (install + pull + jadx + manifest + index):
.\setup-manual.ps1 -Apk C:\apps\target.apk
# dùng máy vật lý đã root:
.\setup-manual.ps1 -Serial <adb-serial>
```

Chuỗi chạy **fail-soft** (bước lỗi hiện lỗi rồi chạy tiếp bước sau):
vendor artifacts → boot AVD (tự root bằng rootAVD nếu chưa có Magisk) →
integrity stack (Zygisk DenyList/Shamiko/PIF/ẩn emulator props) → Burp +
CA vào system store → route proxy → frida-server ẩn + unpin.js → smoke MCP.
Cuối cùng in bảng `[OK]/[FAIL]` từng bước và ghi `workspace/CHEATSHEET.md`
liệt kê mọi lệnh CLI + các đầu giao tiếp cho AI agent.

## Cài đặt

```powershell
pip install -e .
mph doctor
```

## Trạng thái

P1–P4 đã merge vào main (selftest 21/21 xanh): foundation, root/frida ẩn,
RE layer (jadx/manifest/index), screen control + MCP stdio.
Tiếp theo: P5 (audit quality engine), P6 (runner `run.ps1 <apk>` + AI agent).

## Định hướng

Audit bằng AI là việc **sau cùng** — hiện tại bộ công cụ thủ công đã sẵn sàng
(xem "Bắt đầu nhanh" ở trên); các đầu giao tiếp cho AI (MCP stdio qua
`.mcp.json`, Burp MCP :9876, code graph) đã được setup-manual smoke-test sẵn.
