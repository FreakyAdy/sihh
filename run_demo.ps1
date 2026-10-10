# 1-Click PowerShell launcher for IDR Dead Reckoning Web Demo
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "   IDR DEAD RECKONING NAVIGATION — WEB DEMO SERVER" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Starting local presentation server on http://localhost:8080 ..." -ForegroundColor Yellow
Write-Host ""

Start-Process "http://localhost:8080/index.html"

Write-Host "[!] Server is active. Edit files in 'web-demo/' and refresh your browser!" -ForegroundColor Green
Write-Host "[!] Press Ctrl+C in this console to stop the server when done." -ForegroundColor Yellow
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

python -m http.server 8080 --directory web-demo
