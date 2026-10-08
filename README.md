# mph — Mobile Pentest Harness

> **Phạm vi sử dụng:** chỉ dùng kiểm thử an ninh được ủy quyền — app của riêng
> bạn, chương trình bug bounty trong phạm vi cho phép, hoặc môi trường
> lab/CTF. Không dùng nhắm vào hệ thống/người khác khi chưa có sự cho phép.

AI harness cho mobile pentesting (Android): tự động setup emulator root +
bypass (root/SSL/Play Integrity), route traffic qua Burp Suite, decompile &
index mã nguồn (jadx → codebase-memory-mcp), điều khiển màn hình theo tọa độ,
và chạy AI agent (opencode/deepseek) audit + pentest tự động.

## Ràng buộc sử dụng

Harness này **chỉ dùng để phân tích ứng dụng được ủy quyền**: app tự phát triển,
chương trình bug bounty còn scope, CTF/lab, hoặc có hợp đồng kiểm thử.
(Xem spec §1 — `docs/superpowers/specs/2026-10-07-mobile-pentest-harness-design.md`.)

## Bắt đầu nhanh — 1 click (pentest thủ công, không AI)

### 0. Yêu cầu

| Cần | Ghi chú |
|---|---|
| Windows 10/11 x64 | script là PowerShell (.ps1/.cmd) |
| Internet | lần đầu tải ~2GB (system image + vendor artifacts) |
| ~10GB chỗ trống | SDK image + AVD + jadx output |
| **Python 3.12+** cài tay | python.org/downloads — tick **Add to PATH** |
| **Java** cài tay | ví dụ Temurin (adoptium.net) — Burp chạy bằng java |
| **Burp Suite Pro** cài tay | copy `burpsuite_pro.jar` + `BurpLoaderKeygen.jar` vào `C:\Program Files\Burp\bin\BurpSuitePro\` (cần license; máy khác đường dẫn thì sửa `mph.toml` `[paths] burp_bin`) |

(Dùng `-Apk` thì thêm **jadx** — đường dẫn `[re] jadx_bin` trong `mph.toml`.)

### 1. Tải repo về máy

```powershell
git clone https://github.com/oldboysonnt/mobile-harness.git
cd mobile-harness
# hoặc: tải ZIP trên GitHub > Code > Download ZIP, giải nén, mở terminal trong thư mục
```

### 2. Chạy 1 click

```powershell
# double-click setup-manual.cmd, hoặc:
.\setup-manual.ps1
# kèm app đích (install + pull + jadx + manifest + index):
.\setup-manual.ps1 -Apk C:\apps\target.apk
# dùng máy vật lý đã root:
.\setup-manual.ps1 -Serial <adb-serial>
```

**Máy trống (mới cài Windows) cũng chạy được.** Script tự làm:
- thiếu Python packages → tự `pip install -e .`
- chưa có AVD/emulator → tự bootstrap (cmdline-tools + system image API 34
  ~1.5GB + tạo AVD) rồi chạy lại chuỗi — **lần đầu có thể lâu 10–20 phút**,
  các lần sau chỉ vài giây
- doctor in checklist thành phần nào còn thiếu

Chuỗi chạy **fail-soft** (bước lỗi hiện lỗi rồi chạy tiếp bước sau):
vendor artifacts → boot AVD (tự root bằng rootAVD nếu chưa có Magisk) →
integrity stack (Zygisk DenyList/Shamiko/PIF/ẩn emulator props) → Burp +
CA vào system store → route proxy → frida-server ẩn + unpin.js → smoke MCP.
Cuối cùng in bảng `[OK]/[FAIL]` từng bước và ghi `workspace/CHEATSHEET.md`
liệt kê mọi lệnh CLI + các đầu giao tiếp cho AI agent.

### 3. Dùng hằng ngày sau khi setup

Mọi traffic HTTP(S) của emulator đã đi qua Burp (`127.0.0.1:8080`). Lệnh hay
dùng (chi tiết đầy đủ trong `workspace/CHEATSHEET.md`):

```powershell
python -m mph frida unpin <package>   # bypass SSL pinning app đích
python -m mph screen screenshot       # chụp màn hình emulator
python -m mph screen tap 540 1200     # tap theo tọa độ
python -m mph screen ui               # dump UI hierarchy
python -m mph apks list               # danh sách app third-party
python -m mph apks pull <package>     # kéo APK về workspace
python -m mph re jadx <app>           # decompile + index mã nguồn
python -m mph integrity check         # kiểm Play Integrity verdict
python -m mph selftest --phase p4     # selftest toàn chuỗi
python -m mph proxy off               # tắt proxy khi hết việc
```

## Cài đặt (thủ công, không qua ps1)

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
