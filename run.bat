@echo off
chcp 65001 >nul
title 量化选股系统
cd /d %~dp0

echo ============================================
echo   量化选股系统 启动中...
echo ============================================

REM 优先使用项目内虚拟环境 .venv，其次使用系统 python
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.9+ 并加入 PATH。
    echo        或在本目录执行: python -m venv .venv
    pause
    exit /b 1
)

"%PY%" -c "import fastapi, uvicorn, pandas, akshare" >nul 2>&1
if errorlevel 1 (
    echo [提示] 依赖不完整，正在安装 requirements.txt ...
    "%PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请手动执行: "%PY%" -m pip install -r requirements.txt
        pause
        exit /b 1
    )
)

echo   访问地址: http://127.0.0.1:8787
echo   访问密码: 见 config.json（默认 123456）
echo   按 Ctrl+C 停止服务
echo ============================================

"%PY%" -m uvicorn server.main:app --host 0.0.0.0 --port 8787
pause
