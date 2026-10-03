@echo off
rem NOVAPROM: update this clone of the config repository and install the Claude Code environment
rem for the current Windows user (skills, subagents, safety hook, routing rules, settings).
rem Double-click it, or run from cmd. Safe to run again: only changed files are replaced.
rem   install-windows.cmd          install / update
rem   install-windows.cmd -Check   only check what is installed
setlocal
cd /d "%~dp0.."
if exist ".git" (
  where git >nul 2>&1
  if not errorlevel 1 (
    echo Updating the repository ^(git pull^)...
    git pull --ff-only
  )
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-windows.ps1" %*
set RC=%ERRORLEVEL%
echo.
pause
exit /b %RC%
