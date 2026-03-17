@echo off
title Git Auto Add Commit Push

echo ============================================
echo   GIT AUTO PUSH SCRIPT
echo ============================================
echo.

REM Change directory to repo
cd /d D:\Dheeraj-AI-programs-github

echo Current Folder:
cd
echo.

echo ============================================
echo STEP 1 - Checking Git Status
echo ============================================
git status
echo.
pause

echo ============================================
echo STEP 2 - Adding All Changes
echo ============================================
git add .
echo Done.
echo.
pause

echo ============================================
echo STEP 3 - Commit Changes
echo ============================================
set /p msg=Enter commit message: 
git commit -m "%msg%"
echo.
pause

echo ============================================
echo STEP 4 - Push to GitHub
echo ============================================
git push
echo.
pause

echo ============================================
echo   PUSH COMPLETE
echo ============================================
echo Press any key to close...
pause >nul
