#!/bin/bash

# ============================================
# WorkFlow Client Docker 启动脚本
# ============================================
# 支持开发模式（热更新）和生产模式
# 使用方法:
#   ./start_work_flow_client.sh          # 开发模式（默认，支持热更新）
#   ./start_work_flow_client.sh dev      # 开发模式（支持热更新）
#   ./start_work_flow_client.sh down     # 停止并删除容器
# ============================================

# 获取脚本所在目录（deploy目录）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# 项目根目录（deploy的上级目录）
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 默认模式为开发模式
mode="dev"

# 解析命令行参数
if [ -n "$1" ]; then
    case $1 in
        dev|development)
            mode="dev"
            ;;
        down|stop)
            echo "🛑 停止并删除容器..."
            cd "$SCRIPT_DIR"
            docker-compose -f docker-compose.yml down
            echo "✅ 容器已停止"
            exit 0
            ;;
        logs)
            echo "📋 查看容器日志..."
            cd "$SCRIPT_DIR"
            docker-compose -f docker-compose.yml logs -f
            exit 0
            ;;
        restart)
            echo "🔄 重启容器..."
            cd "$SCRIPT_DIR"
            docker-compose -f docker-compose.yml restart
            echo "✅ 容器已重启"
            exit 0
            ;;
        *)
            echo "❌ 未知参数: $1"
            echo "使用方法:"
            echo "  ./start_work_flow_client.sh         # 启动开发模式（热更新）"
            echo "  ./start_work_flow_client.sh dev     # 启动开发模式（热更新）"
            echo "  ./start_work_flow_client.sh down    # 停止并删除容器"
            echo "  ./start_work_flow_client.sh logs    # 查看日志"
            echo "  ./start_work_flow_client.sh restart # 重启容器"
            exit 1
            ;;
    esac
fi

echo "===================================="
echo "🚀 启动 WorkFlow Client - 开发模式"
echo "===================================="
echo "📁 项目根目录: $PROJECT_ROOT"
echo "🔧 构建模式: dev-hot-reload (支持热更新)"
echo ""

# 切换到项目根目录进行构建
cd "$PROJECT_ROOT"

echo "📦 构建开发镜像..."
docker build \
    -t work_flow_client:dev \
    --target dev-hot-reload \
    -f deploy/Dockerfile \
    . || {
        echo "❌ 镜像构建失败"
        exit 1
    }

echo ""
echo "🐳 启动容器..."

# 切换到 deploy 目录启动 compose
cd "$SCRIPT_DIR"
docker-compose -f docker-compose.yml up -d || {
    echo "❌ 容器启动失败"
    exit 1
}

echo ""
echo "✅ WorkFlow Client 启动完成！"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📍 访问地址: http://localhost:8000"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 提示："
echo "  • 修改源代码后会自动热更新"
echo "  • 查看日志: ./start_work_flow_client.sh logs"
echo "  • 重启服务: ./start_work_flow_client.sh restart"
echo "  • 停止服务: ./start_work_flow_client.sh down"
echo ""
