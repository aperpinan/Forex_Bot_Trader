@echo off
rem Starts the RSI bot in the background (no window). Its log is bot.log in this folder.
cd /d "%~dp0"
if exist STOP.txt del STOP.txt
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0bot.py"
echo Bot started. Log: %~dp0bot.log
timeout /t 3 >nul
