<#
.SYNOPSIS
    一键启动「学生管理系统」的前后端（开发环境）。

.DESCRIPTION
    做三件事：
      1. 检查 Node 版本、Python 虚拟环境、数据库配置，缺什么就明确提示什么
      2. 后台拉起 FastAPI（127.0.0.1:8003），等它真正能响应了再继续
      3. 前台拉起 Vite（localhost:5173），Ctrl+C 一起停掉

    这个脚本只是「方便」，不是必须的 —— README 里也有分开敲的等价命令。

.EXAMPLE
    .\scripts\start-all.ps1

.EXAMPLE
    .\scripts\start-all.ps1 -SkipBackend     # 只起前端（后端已经在跑了）
#>
[CmdletBinding()]
param(
    # 后端已经手动跑着的时候，加这个参数跳过启动后端
    [switch]$SkipBackend
)

$ErrorActionPreference = 'Stop'

$frontendDir = Split-Path -Parent $PSScriptRoot
$projectRoot = Split-Path -Parent $frontendDir

function Write-Step  { param($m) Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Write-Ok    { param($m) Write-Host "  [OK]   $m" -ForegroundColor Green }
function Write-Warn  { param($m) Write-Host "  [警告] $m" -ForegroundColor Yellow }
function Write-Err   { param($m) Write-Host "  [错误] $m" -ForegroundColor Red }

# ---------------------------------------------------------------------
# 1. Node 环境
# ---------------------------------------------------------------------
Write-Step "检查 Node 环境"

# Windows 上 Node 常常装在 C:\Program Files\nodejs 但不在当前 shell 的 PATH 里
$nodeHome = 'C:\Program Files\nodejs'
if (-not (Get-Command node -ErrorAction SilentlyContinue) -and (Test-Path $nodeHome)) {
    $env:PATH = "$nodeHome;$env:PATH"
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Err "找不到 node。请先安装 Node.js LTS：https://nodejs.org/"
    Write-Host "        装完【必须新开一个终端】再运行本脚本（PATH 不会自动刷新）。"
    exit 1
}

$nodeVersion = (& node -v) -replace '^v', ''
$parts = $nodeVersion.Split('.')
$major = [int]$parts[0]
$minor = [int]$parts[1]

# Vite 8 的硬性要求：^20.19.0 || >=22.12.0
$nodeOk = ($major -eq 20 -and $minor -ge 19) -or $major -ge 22
if (-not $nodeOk) {
    Write-Err "Node 版本过低：$nodeVersion"
    Write-Host "        Vite 8 要求 ^20.19.0 或 >=22.12.0，请升级到 Node LTS。"
    exit 1
}
Write-Ok "Node $nodeVersion（满足 Vite 8 的 ^20.19.0 || >=22.12.0）"

# ---------------------------------------------------------------------
# 2. 前端依赖
# ---------------------------------------------------------------------
Write-Step "检查前端依赖"

if (-not (Test-Path (Join-Path $frontendDir 'node_modules'))) {
    Write-Warn "还没装前端依赖，正在执行 npm install（首次会比较久）..."
    Push-Location $frontendDir
    try {
        & npm.cmd install
        if ($LASTEXITCODE -ne 0) { Write-Err "npm install 失败"; exit 1 }
    } finally { Pop-Location }
}
Write-Ok "node_modules 就绪"

# ---------------------------------------------------------------------
# 3. 后端环境
# ---------------------------------------------------------------------
Write-Step "检查后端环境"

$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$backendProcess = $null
$logDir = Join-Path $frontendDir '.runtime'
$logFile = Join-Path $logDir 'backend.log'

if ($SkipBackend) {
    Write-Ok "已指定 -SkipBackend，跳过后端启动"
} else {
    if (-not (Test-Path $pythonExe)) {
        Write-Err "找不到虚拟环境：.venv"
        Write-Host "        请先在项目根目录执行："
        Write-Host "            python -m venv .venv"
        Write-Host "            .\.venv\Scripts\pip install -r requirements.txt"
        exit 1
    }
    Write-Ok "Python 虚拟环境就绪"

    $envFile = Join-Path $projectRoot '.env'
    if (-not (Test-Path $envFile)) {
        Write-Warn "项目根目录没有 .env（数据库配置）。"
        Write-Host "        需要自己填这 5 项：DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD"
    } else {
        Write-Ok "数据库配置 .env 就绪"
    }

    New-Item -ItemType Directory -Force -Path $logDir | Out-Null

    Write-Host "  正在启动 FastAPI (127.0.0.1:8003) ..."
    $backendProcess = Start-Process -FilePath $pythonExe `
        -ArgumentList '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8003' `
        -WorkingDirectory $projectRoot `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError (Join-Path $logDir 'backend.err.log') `
        -PassThru -WindowStyle Hidden

    # 等后端真的能响应（先等服务本身，再试一次真的查库的那个接口）
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        if ($backendProcess.HasExited) { break }
        try {
            $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8003/openapi.json' -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) {
                $ready = $true
                # 再确认数据库能连上（能返回 JSON 而不是 500）
                try {
                    $d = Invoke-WebRequest -Uri 'http://127.0.0.1:8003/student/select_stu_skip?skip=0&limit=1' -UseBasicParsing -TimeoutSec 5
                    if ($d.StatusCode -eq 200) {
                        Write-Ok "后端已就绪，数据库连接正常"
                    } else {
                        Write-Warn "后端起来了，但数据库查询返回 $($d.StatusCode)，请看日志"
                    }
                } catch {
                    Write-Warn "后端起来了，但数据库查询失败，请看 $logFile"
                }
                break
            }
        } catch { }
    }

    if (-not $ready) {
        Write-Err "后端 20 秒内没起来。最后 30 行日志："
        if (Test-Path $logFile) { Get-Content $logFile -Tail 30 }
        if (Test-Path (Join-Path $logDir 'backend.err.log')) {
            Get-Content (Join-Path $logDir 'backend.err.log') -Tail 30
        }
        exit 1
    }
}

# ---------------------------------------------------------------------
# 4. 前端
# ---------------------------------------------------------------------
Write-Step "启动前端开发服务器"
Write-Host "  前端地址: http://localhost:5173"
Write-Host "  演示账号: 任意账号密码都能进（预填 admin / 123456）"
Write-Host "  按 Ctrl+C 停止`n"

Push-Location $frontendDir
try {
    & npm.cmd run dev
} finally {
    Pop-Location

    # Ctrl+C 之后把后台的后端一起收掉，避免留一堆僵尸进程
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Write-Host "`n正在停止后端 ..."
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }
}
