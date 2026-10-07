# mph — Mobile Pentest Harness

AI harness cho mobile pentesting (Android): tự động setup emulator root +
bypass (root/SSL/Play Integrity), route traffic qua Burp Suite, decompile &
index mã nguồn (jadx → codebase-memory-mcp), điều khiển màn hình theo tọa độ,
và chạy AI agent (opencode/deepseek) audit + pentest tự động.

## Ràng buộc sử dụng

Harness này **chỉ dùng để phân tích ứng dụng được ủy quyền**: app tự phát triển,
chương trình bug bounty còn scope, CTF/lab, hoặc có hợp đồng kiểm thử.
(Xem spec §1 — `docs/superpowers/specs/2026-10-07-mobile-pentest-harness-design.md`.)

## Cài đặt

```powershell
pip install -e .
mph doctor
```

## Trạng thái

P1 (foundation) đang được triển khai theo plan
`docs/superpowers/plans/2026-10-07-mobile-harness-p1-foundation.md`.
