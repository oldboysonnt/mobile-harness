---
name: mp-audit
description: Audit bảo mật app mobile theo MASTG 4-pass (static + dynamic) và xuất findings có evidence — bản outline (engine đầy đủ ở P5).
---

# mp-audit (outline — P5 sẽ hoàn thiện engine + benchmark)

Với workspace `<app>` đã recon:

- Pass 1 — Surface: manifest.json (exported/aliases/authorities/deeplinks).
- Pass 2 — Static: codebase-memory queries cho M1-M10 (secrets, crypto yếu,
  storage, WebView, IPC, logging nhạy cảm).
- Pass 3 — Dynamic: mp-traffic + lái app qua MCP mph (screenshot→tap);
  hook frida khi app detect root/pinning.
- Pass 4 — Verifier: mỗi candidate finding phải repro được (static: file:line;
  dynamic: HTTP transcript + screenshot). Bác bỏ thì ghi lý do.

Findings format: workspace/<app>/findings.md — title / severity / evidence /
repro / remediation. Ràng buộc: chỉ audit app được ủy quyền.
