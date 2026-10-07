#!/usr/bin/env python
import json, sys

def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    mid = msg.get("id")
    m = msg.get("method")
    if m == "initialize":
        send({"jsonrpc": "2.0", "id": mid,
              "result": {"protocolVersion": "2024-11-05", "capabilities": {}}})
    elif m == "tools/call":
        args = msg.get("params", {}).get("arguments", {})
        if str(args.get("repo_path", "")).endswith("fail"):
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "isError": True,
                "content": [{"type": "text", "text": "Error: boom"}]}})
        else:
            send({"jsonrpc": "2.0", "id": mid, "result": {"content": [
                {"type": "text", "text": json.dumps({"status": "ok", "nodes": 100})}]}})
