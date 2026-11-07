# 启动「小管家」知识库小助手服务（后台常驻）
#
# 为什么不用前台运行：
#   会话里直接跑 uvicorn，宿主的后台任务有 1 小时硬上限，到点会把进程一起回收，
#   表现为「刚还好好的，小助手突然就没了」。Start-Process 起独立进程，
#   不受这个上限影响，关掉终端也继续跑。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File .\kb_assistant\start.ps1
#   powershell -ExecutionPolicy Bypass -File .\kb_assistant\stop.ps1

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
$py   = Join-Path $root '.venv\Scripts\python.exe'
$logDir = Join-Path $here 'logs'

if (-not (Test-Path $py)) {
    Write-Host "找不到虚拟环境解释器：$py" -ForegroundColor Red
    exit 1
}

# 已经在跑就别重复启动
try {
    $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8010/health' -TimeoutSec 2
    Write-Host '小助手已在运行： http://127.0.0.1:8010' -ForegroundColor Green
    exit 0
} catch {
    # 没在跑，继续往下走
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# 让 Python 用 UTF-8 输出，否则中文日志在控制台是乱码
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

$proc = Start-Process -FilePath $py `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8010', '--log-level', 'info' `
    -WorkingDirectory $here `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir 'server.out.log') `
    -RedirectStandardError  (Join-Path $logDir 'server.err.log') `
    -PassThru

Start-Sleep -Seconds 3
try {
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8010/health' -TimeoutSec 5
    Write-Host "小助手已启动： http://127.0.0.1:8010  (PID $($proc.Id))" -ForegroundColor Green
    Write-Host "  模型：$($health.config.model)   数据库：$($health.config.database)   连通：$($health.database_connected)"
    Write-Host "  日志：$logDir"
} catch {
    Write-Host "启动后健康检查没通过，请看日志：$logDir" -ForegroundColor Yellow
    exit 1
}
