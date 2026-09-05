@echo off
title PLOT: The Cultural Atlas - Local Preview Server
cls
echo =====================================================================
echo   PLOT: The Cultural Atlas - Local Development Server
echo =====================================================================
echo.
echo Checking Python environment...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not found in your PATH. Please install Python 3.
    pause
    exit /b 1
)

echo Starting local preview server on http://127.0.0.1:8000 ...
echo (Your default browser will open automatically with hot-reload enabled)
echo.
python "%~dp0serve_preview.py"
pause
