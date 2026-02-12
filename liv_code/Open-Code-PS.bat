@echo off
set TARGET=D:\OneDrive-Local\OneDrive\DheerajOnHP\AI_assisted_project_docs

:: Launch Windows Terminal as Administrator with PowerShell in target folder
powershell -Command ^
    "Start-Process wt -Verb RunAs -ArgumentList 'powershell -NoExit -Command Set-Location ''%TARGET%'''"

exit
