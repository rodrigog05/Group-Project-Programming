@echo off
setlocal
set "game_runtime=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%game_runtime%" (
    "%game_runtime%" "%~dp0tycoon.py"
    exit /b
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0tycoon.py"
    if not errorlevel 1 exit /b
)
python "%~dp0tycoon.py"
if errorlevel 1 pause
