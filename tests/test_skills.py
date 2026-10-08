# tests/test_skills.py
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

def test_skills_exist_with_frontmatter():
    for name in ("mp-setup", "mp-recon", "mp-traffic", "mp-audit"):
        f = REPO / "skills" / name / "SKILL.md"
        assert f.exists(), name
        head = f.read_text(encoding="utf-8")[:200]
        assert head.startswith("---") and "name:" in head

def test_mcp_json_shape():
    d = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))
    assert "mph" in d["mcpServers"]
