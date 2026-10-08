"""Cho phép `python -m mph ...` — setup-manual.ps1 gọi dạng này khi
console-script `mph` chua duoc pip install len PATH."""
from .cli import app

app()
