import json, sys
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("method") == "initialize":
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"],
            "result": {}}) + "\n")
        sys.stdout.flush()
    break  # chết sau initialize
