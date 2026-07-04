#!/bin/bash

# 默认模式为develop
mode="develop"

# 解析传入的模式参数
if [ -n "$1" ]; then
    case $1 in
        publish)
            mode="publish"
            ;;
        develop)
            mode="develop"
            ;;
        develop_home)
            mode="develop_home"
            ;;
        down)
            # 保留原有的down参数处理
            docker compose -f deploy/work_flow_client.yml down
            exit 0
            ;;
    esac
fi

# 获取脚本所在目录（deploy目录）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# 项目根目录（deploy的上级目录）
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "start_work_flow_client 开始构建 $mode 环境镜像..."
echo "项目根目录: $PROJECT_ROOT"

# 从项目根目录构建
cd "$PROJECT_ROOT"
docker build \
    -t work_flow_client:latest . --target $mode -f deploy/Dockerfile

# 从 deploy 目录启动 compose
cd "$SCRIPT_DIR"
docker-compose -f work_flow_client.yml up -d -V
