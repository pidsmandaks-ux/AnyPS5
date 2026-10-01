@echo off
setlocal
cd /d "%~dp0.."
where py >nul 2>nul
if %errorlevel%==0 (
    py tools\anyps5_gui.py
    exit /b %errorlevel%
)
where python >nul 2>nul
if %errorlevel%==0 (
    python tools\anyps5_gui.py
    exit /b %errorlevel%
)
echo Python was not found.
echo Install Python 3 with Tkinter, then run this launcher again.
pause
exit /b 1
