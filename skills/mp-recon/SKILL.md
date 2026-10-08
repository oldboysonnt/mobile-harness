---
name: mp-recon
description: Đọc hiểu một app Android — pull APK, jadx, manifest attack-surface, index codebase-memory để tra cứu ngữ nghĩa.
---

# mp-recon

Với package mục tiêu `<pkg>`:

1. `mph apks pull <pkg>` → workspace `<pkg_underscore>/apk/`.
2. `mph re jadx <app>` — decompile (idempotent).
3. `mph re manifest <app>` — attack surface: exported components, aliases,
   provider authorities, deeplinks, permissions, flags.
4. `mph re index <app>` — index codebase-memory (moderate).

Sau đó query bằng MCP codebase-memory: `search_graph` (tìm hàm/class),
`trace_path` (call chain), `query_graph` (Cypher), `get_architecture`.
Tập trung: điểm implement certificate pinning, root/integrity detection,
hardcoded secrets, WebView config, IPC/deeplink handlers.
