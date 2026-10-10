@echo off
title IDR Navigation Web Demo (Frontend Dev Server)
cls
echo ================================================================
echo    IDR DEAD RECKONING NAVIGATION — WEB DEMO SERVER
echo ================================================================
echo.
echo Starting local presentation server on http://localhost:8080 ...
echo.
echo Launching your browser at http://localhost:8080/index.html ...
start http://localhost:8080/index.html
echo.
echo [!] Server is active with Live Phone Bridge support!
echo [!] Press Ctrl+C in this window to stop the server when done.
echo ================================================================
echo.

python scripts/live_sensor_bridge.py
pause
