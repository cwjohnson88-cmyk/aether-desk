@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" launch_dashboard.py
) else (
  start "" pythonw.exe launch_dashboard.py
)
