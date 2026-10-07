# Fingerprints pool (PIF / PlayIntegrityFix)

Mỗi file `<tên>.json` là một device fingerprint cho module PIF
(osm0sis/PlayIntegrityFork). Khi `mph root install` chạy, fingerprint **đầu
tiên theo thứ tự alphabet** được áp dụng tự động; đổi bằng:

```
mph integrity use-fingerprint <tên>
```

## Định dạng (ví dụ `pixel8.json`)

```json
{
  "MANUFACTURER": "Google",
  "MODEL": "Pixel 8",
  "FINGERPRINT": "google/.../...:14/UPB4/...",
  "BRAND": "google",
  "PRODUCT": "...",
  "DEVICE": "...",
  "SECURITY_PATCH": "2026-09-05",
  "FIRST_API_LEVEL": "34"
}
```

## Nguồn fingerprint

- Lấy từ device thật (Build.getprop) hoặc các nguồn cộng đồng còn hoạt động.
- Fingerprint bị Google **ban theo đợt** → giữ nhiều bản dự phòng trong thư
  mục này; khi verdict tụt (kiểm tra bằng SPIC — `mph integrity check` từ P4),
  đổi sang bản khác.

Lưu ý: KHÔNG commit fingerprint thật nhạy cảm vào repo công khai.
