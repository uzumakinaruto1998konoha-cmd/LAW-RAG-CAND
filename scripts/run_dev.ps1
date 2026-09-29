# Script chạy ứng dụng LAW-RAG-CAND trên Windows PowerShell
# Chạy cả Backend API và Web UI phục vụ tại http://127.0.0.1:8000

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir

Set-Location $RootDir

$port = if ($env:LAW_RAG_API_PORT) { [int]$env:LAW_RAG_API_PORT } else { 8000 }
$existing = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    $pidToKill = $existing.OwningProcess
    Write-Host "Phát hiện tiến trình (PID $pidToKill) đang chiếm cổng $port. Đang giải phóng..." -ForegroundColor Yellow
    Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

Write-Host "Kiểm tra kiểm thử backend..." -ForegroundColor Cyan
py -m unittest discover -s tests

if ($LASTEXITCODE -ne 0) {
    Write-Host "Kiểm thử backend thất bại! Dừng khởi chạy." -ForegroundColor Red
    exit 1
}

Write-Host "Khởi động ứng dụng LAW-RAG-CAND..." -ForegroundColor Green
py scripts/run_app.py

