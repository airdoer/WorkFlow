#!/bin/bash
set -e

COMPOSE_FILE=./redis_cluster.yml

if [ "$1" == "down" ]; then
    echo "🛑 停止并清理 Redis Cluster..."
    docker compose -f $COMPOSE_FILE down --remove-orphans -v
    exit 0
fi

echo "🚀 启动 Redis Cluster 容器..."
docker compose -f $COMPOSE_FILE up -d

mkdir -p ./redis/data/master1
mkdir -p ./redis/data/master2
mkdir -p ./redis/data/master3
chmod -R 777 ./redis/data

echo "⏳ 等待 Redis 节点启动..."
sleep 8

echo "⚙️ 初始化 Redis Cluster..."
docker compose -f $COMPOSE_FILE --profile init up -d

echo "✅ Redis Cluster 已启动完成！"
