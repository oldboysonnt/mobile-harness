@echo off
rem setup-manual.cmd - double-click chay setup-manual.ps1 (khong can doi ExecutionPolicy)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-manual.ps1" %*
