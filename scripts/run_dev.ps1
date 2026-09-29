# Script chạy ứng dụng LAW-RAG-CAND trên Windows PowerShell
# Chạy cả Backend API và Web UI phục vụ tại http://127.0.0.1:8000

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir

Set-Location $RootDir

Write-Host "Kiểm tra kiểm thử backend..." -ForegroundColor Cyan
py -m unittest discover -s tests

if ($LASTEXITCODE -ne 0) {
    Write-Host "Kiểm thử backend thất bại! Dừng khởi chạy." -ForegroundColor Red
    exit 1
}

Write-Host "Khởi động ứng dụng LAW-RAG-CAND..." -ForegroundColor Green
py scripts/run_app.py
