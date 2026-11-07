# 停止「小管家」知识库小助手服务
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File .\kb_assistant\stop.ps1

$ErrorActionPreference = 'SilentlyContinue'

$targets = Get-CimInstance Win32_Process -Filter "Name like '%python%'" | Where-Object {
    $_.CommandLine -match 'uvicorn\s+app\.main:app' -and $_.CommandLine -match '8010'
}

if (-not $targets) {
    Write-Host '小助手当前没有在运行。' -ForegroundColor Yellow
    exit 0
}

foreach ($t in $targets) {
    Stop-Process -Id $t.ProcessId -Force
    Write-Host "已停止 PID $($t.ProcessId)" -ForegroundColor Green
}
