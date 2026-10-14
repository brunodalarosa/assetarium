@echo off
setlocal
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
cd /d "%~dp0"
echo Generate pending asset descriptions with the local model; existing faults are retained.
echo Keep this window open. Progress and a morning report are saved automatically.
echo.
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\overnight-descriptions.py" --pending-only --peak-reserve-mib 1024 %*
set "overnight_result=%errorlevel%"
echo.
echo See data\overnight-descriptions\latest.json for the run folder and morning report.
echo You can close this window after the run finishes.
pause
exit /b %overnight_result%
