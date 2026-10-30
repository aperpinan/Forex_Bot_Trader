@echo off
rem Opens the bot web panel at http://localhost:8282 (this PC; other devices use http://<PC IP>:8282 with PANEL_PASSWORD from .env). Closing the browser keeps it running.
cd /d "%~dp0"
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0panel.py"
echo Panel: http://localhost:8282
timeout /t 3 >nul
