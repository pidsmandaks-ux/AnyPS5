@echo off
setlocal
py "%~dp0anyps5_gui.py"
if errorlevel 1 (
    echo.
    echo AnyPS5 GUI could not be started.
    pause
)
