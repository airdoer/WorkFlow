@echo off
REM MongoDB集群初始化脚本 (Windows版本)
REM 用于快速执行MongoDB初始化

setlocal enabledelayedexpansion

echo MongoDB集群初始化脚本 (Windows)
echo ================================
echo.

REM 获取脚本目录
set "SCRIPT_DIR=%~dp0"
set "SERVER_DIR=%SCRIPT_DIR%.."

echo 脚本目录: %SCRIPT_DIR%
echo 服务器目录: %SERVER_DIR%
echo.

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到python命令
    pause
    exit /b 1
)

echo ✅ Python环境检查通过

REM 检查依赖
echo 检查Python依赖...
cd /d "%SERVER_DIR%"

if not exist "requirements.txt" (
    echo ❌ 错误: 未找到requirements.txt文件
    pause
    exit /b 1
)

REM 检查pymongo是否已安装
python -c "import pymongo" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  警告: pymongo未安装，正在安装依赖...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ 错误: 依赖安装失败
        pause
        exit /b 1
    )
) else (
    echo ✅ pymongo依赖检查通过
)

REM 执行初始化脚本
echo.
echo 开始执行MongoDB初始化...
echo ========================

cd /d "%SCRIPT_DIR%"
python init_mongodb_cluster.py

if errorlevel 1 (
    echo.
    echo ❌ 初始化脚本执行失败!
    pause
    exit /b 1
)

echo.
echo ✅ 初始化脚本执行完成!
pause