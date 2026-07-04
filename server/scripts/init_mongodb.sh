#!/bin/bash

# MongoDB集群初始化脚本
# 用于快速执行MongoDB初始化

set -e  # 遇到错误立即退出

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(dirname "$SCRIPT_DIR")"

echo "MongoDB集群初始化脚本"
echo "===================="
echo "脚本目录: $SCRIPT_DIR"
echo "服务器目录: $SERVER_DIR"
echo ""

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到python3命令"
    exit 1
fi

echo "✅ Python3环境检查通过"

# 检查依赖
echo "检查Python依赖..."
cd "$SERVER_DIR"

if [ ! -f "requirements.txt" ]; then
    echo "❌ 错误: 未找到requirements.txt文件"
    exit 1
fi

# 检查pymongo是否已安装
if ! python3 -c "import pymongo" &> /dev/null; then
    echo "⚠️  警告: pymongo未安装，正在安装依赖..."
    pip3 install -r requirements.txt
else
    echo "✅ pymongo依赖检查通过"
fi

# 执行初始化脚本
echo ""
echo "开始执行MongoDB初始化..."
echo "========================"

cd "$SCRIPT_DIR"
python3 init_mongodb_cluster.py

echo ""
echo "初始化脚本执行完成!"