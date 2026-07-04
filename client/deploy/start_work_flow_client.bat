@echo off
REM ============================================
REM WorkFlow Client Docker 启动脚本 (Windows)
REM ============================================
REM 支持开发模式（热更新）
REM 使用方法:
REM   start_work_flow_client.bat          # 启动开发模式
REM   start_work_flow_client.bat down     # 停止容器
REM ============================================

cd /d "%~dp0"

if "%1"=="down" goto stop
if "%1"=="stop" goto stop
if "%1"=="logs" goto logs
if "%1"=="restart" goto restart

:start
echo ====================================
echo 🚀 启动 WorkFlow Client - 开发模式
echo ====================================
echo.

echo 📦 构建开发镜像...
cd ..
docker build -t work_flow_client:dev --target dev-hot-reload -f deploy/Dockerfile . || (
    echo ❌ 镜像构建失败
    pause
    exit /b 1
)

echo.
echo 🐳 启动容器...
cd deploy
docker-compose -f docker-compose.yml up -d || (
    echo ❌ 容器启动失败
    pause
    exit /b 1
)

echo.
echo ✅ WorkFlow Client 启动完成！
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo 📍 访问地址: http://localhost:8000
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo 💡 提示：
echo   • 修改源代码后会自动热更新
echo   • 查看日志: start_work_flow_client.bat logs
echo   • 重启服务: start_work_flow_client.bat restart
echo   • 停止服务: start_work_flow_client.bat down
echo.
pause
exit /b 0

:stop
echo 🛑 停止并删除容器...
docker-compose -f docker-compose.yml down
echo ✅ 容器已停止
pause
exit /b 0

:logs
echo 📋 查看容器日志...
docker-compose -f docker-compose.yml logs -f
exit /b 0

:restart
echo 🔄 重启容器...
docker-compose -f docker-compose.yml restart
echo ✅ 容器已重启
pause
exit /b 0
