@echo off
REM Simple git commit script for Windows

if "%~1"=="" (
    echo Usage: commit.bat "Your commit message"
    echo Example: commit.bat "Fix CI workflow"
    exit /b 1
)

git commit -m "%~1"
