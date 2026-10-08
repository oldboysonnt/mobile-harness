---
name: mp-traffic
description: Bắt và phân tích traffic HTTPS của app qua Burp (unpin nếu cần), đọc history qua Burp MCP.
---

# mp-traffic

1. `mph burp start` + `mph proxy on` + `mph cert` (nếu chưa).
2. Mở app mục tiêu qua MCP mph (screenshot → tap icon).
3. Nếu app fail mạng: `mph frida unpin <pkg>` (bypass SSL pinning).
4. Đọc history: Burp MCP native port 9876 (`mph/proxy/burp_mcp.py`
   `BurpMcp.call`); hoặc mở Burp UI xem Proxy → HTTP history.
5. Tìm: auth token trong URL/body, endpoint IDOR tiềm năng, leak dữ liệu,
   API không có rate limit. `mph proxy off` khi xong.
