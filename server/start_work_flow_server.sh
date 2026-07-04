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
            docker-compose -f work_flow_server.yml down
            exit 0
            ;;
    esac
fi

echo "work_flow_server 开始构建 $mode 环境镜像..."
docker build \
    -t work_flow_server ./ --target $mode -f ./Dockerfile

export WATCHMAN_TAG="hotfix"
docker-compose -f work_flow_server.yml up -d
