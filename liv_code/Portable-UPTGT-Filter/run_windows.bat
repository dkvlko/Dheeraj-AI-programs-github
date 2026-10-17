@echo off
cd /d "%~dp0"

echo Starting Question Reviewer...
echo.

python app.py

echo.
echo Press any key to exit...
pause >nul
