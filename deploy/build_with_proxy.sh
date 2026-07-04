#!/bin/bash

# Docker 代理配置脚本
# 用于在公司内网环境下构建 Docker 镜像

# 设置代理环境变量
export http_proxy="http://10.52.57.90:11080"
export https_proxy="http://10.52.57.90:11080"
export HTTP_PROXY="http://10.52.57.90:11080"
export HTTPS_PROXY="http://10.52.57.90:11080"
export no_proxy="localhost,127.0.0.1,localaddress,localdomain.com,.internal,.corp.kuaishou.com,.test.gifshow.com,.staging.kuaishou.com"
export NO_PROXY="localhost,127.0.0.1,localaddress,localdomain.com,.internal,.corp.kuaishou.com,.test.gifshow.com,.staging.kuaishou.com"

echo "已设置 Docker 构建代理"
echo "http_proxy: $http_proxy"
echo "https_proxy: $https_proxy"

# 切换到项目根目录
cd "$(dirname "$0")/.."
echo "当前目录: $(pwd)"

# 现在可以构建镜像（从项目根目录构建）
echo "执行: docker build -t work_flow_client:latest . --target develop -f deploy/Dockerfile"
docker build -t work_flow_client:latest . --target develop -f deploy/Dockerfile
