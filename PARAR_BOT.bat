@echo off
rem Stops the RSI bot. Open trades stay open with their stop-loss and take-profit on tastyfx's server.
cd /d "%~dp0"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" | Where-Object { $_.CommandLine -like '*Forex_Bot_Trader\bot.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; 'stopped ' + $_.ProcessId }"
echo [%date% %time%] stopped with PARAR_BOT.bat>> bot.log
timeout /t 3 >nul
