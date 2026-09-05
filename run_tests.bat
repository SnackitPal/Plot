@echo off
title PLOT: Automated Test Suite (TDD)
cls
echo =====================================================================
echo   PLOT: Automated Algorithmic & Geospatial Test Suite
echo =====================================================================
echo.
if not exist "%~dp0.venv\Scripts\pytest.exe" (
    echo [ERROR] Virtual environment not found.
    pause
    exit /b 1
)

"%~dp0.venv\Scripts\pytest.exe" -v
echo.
echo =====================================================================
pause
