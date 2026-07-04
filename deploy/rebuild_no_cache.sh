#!/bin/bash

# 强制重新构建脚本（不使用缓存）

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
    esac
fi

# 获取脚本所在目录（deploy目录）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# 项目根目录（deploy的上级目录）
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "==============================================="
echo "强制重新构建 $mode 环境镜像（无缓存）..."
echo "项目根目录: $PROJECT_ROOT"
echo "==============================================="

# 停止现有容器
echo "1. 停止现有容器..."
cd "$SCRIPT_DIR"
docker-compose -f work_flow_client.yml down

# 删除旧镜像
echo "2. 删除旧镜像..."
docker rmi work_flow_client:latest 2>/dev/null || echo "旧镜像不存在，跳过删除"

# 从项目根目录构建（不使用缓存）
echo "3. 开始构建新镜像（不使用缓存）..."
cd "$PROJECT_ROOT"
docker build --no-cache \
    -t work_flow_client:latest . --target $mode -f deploy/Dockerfile

# 检查构建是否成功
if [ $? -eq 0 ]; then
    echo "4. 构建成功，启动容器..."
    # 从 deploy 目录启动 compose
    cd "$SCRIPT_DIR"
    docker-compose -f work_flow_client.yml up -d -V
    
    echo "==============================================="
    echo "部署完成！"
    echo "访问地址: http://172.28.200.60:8000"
    echo "==============================================="
else
    echo "==============================================="
    echo "构建失败！请检查错误信息。"
    echo "==============================================="
    exit 1
fi
