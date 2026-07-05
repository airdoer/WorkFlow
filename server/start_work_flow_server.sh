#!/bin/bash

echo "work_flow_server 开始构建 环境镜像..."
docker build \
    --network=host \
    --no-cache \
    --build-arg http_proxy=http://10.52.57.90:11080 \
    --build-arg https_proxy=http://10.52.57.90:11080 \
    -t work_flow_server ./ -f ./Dockerfile

export WATCHMAN_TAG="hotfix"
docker-compose -f work_flow_server.yml up -d
