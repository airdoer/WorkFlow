# Docker 构建故障排查

## 常见错误及解决方案

### 1. 错误：`"/deploy/start.sh": not found`

**原因**：构建上下文路径不正确

**解决方案**：
- ✅ 使用提供的脚本：`cd deploy && ./start_work_flow_client.sh develop`
- ✅ 手动构建时，必须在项目根目录执行：
  ```bash
  cd /data/chenzhixu/WorkFlow  # 项目根目录
  docker build -t work_flow_client:latest . --target develop -f deploy/Dockerfile
  ```
- ❌ 错误做法：在 deploy 目录下执行 `docker build -t xxx ./ -f ./Dockerfile`

### 2. 错误：`failed to fetch oauth token` 或网络超时

**原因**：无法连接到 Docker Hub

**解决方案**：

#### 方案 A：使用国内镜像源（推荐）
```bash
# 1. 编辑 Docker 配置
sudo vim /etc/docker/daemon.json

# 2. 添加以下内容
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com"
  ]
}

# 3. 重启 Docker
sudo systemctl restart docker

# 4. 重新构建
cd /data/chenzhixu/WorkFlow/deploy
./start_work_flow_client.sh develop
```

#### 方案 B：使用代理
```bash
cd /data/chenzhixu/WorkFlow/deploy
chmod +x build_with_proxy.sh
./build_with_proxy.sh
```

#### 方案 C：预先拉取镜像
```bash
# 在网络好的机器上
docker pull node:22-alpine
docker save node:22-alpine > node-22-alpine.tar

# 传输到目标机器
scp node-22-alpine.tar user@target:/tmp/

# 在目标机器上导入
docker load < /tmp/node-22-alpine.tar
```

### 3. 错误：`COPY failed` 或文件找不到

**检查清单**：
- [ ] 确认在项目根目录有 `package.json` 和 `package-lock.json`
- [ ] 确认 `deploy/start.sh` 文件存在
- [ ] 确认构建命令的上下文路径正确

**正确的构建命令**：
```bash
# 上下文是 . (项目根目录)，Dockerfile 在 deploy/ 目录
docker build -t work_flow_client:latest . -f deploy/Dockerfile --target develop
```

### 4. 错误：`npm install` 失败

**原因**：网络问题或依赖冲突

**解决方案**：
```bash
# 使用淘宝镜像
修改 Dockerfile，在 npm install 前添加：
RUN npm config set registry https://registry.npmmirror.com
```

### 5. 容器启动后无法访问

**检查清单**：
- [ ] 检查容器是否运行：`docker ps | grep work_flow_client`
- [ ] 检查端口映射：`docker port work_flow_client_container`
- [ ] 检查容器日志：`docker logs work_flow_client_container`
- [ ] 检查网络：`docker network inspect redis-cluster-network`

**创建网络（如果不存在）**：
```bash
docker network create redis-cluster-network
```

## 调试命令

```bash
# 查看构建过程
docker build -t work_flow_client:latest . -f deploy/Dockerfile --target develop --progress=plain

# 进入容器调试
docker run -it --rm work_flow_client:latest sh

# 查看容器日志
docker logs -f work_flow_client_container

# 查看容器环境变量
docker exec work_flow_client_container env

# 检查 env-config.js 是否生成
docker exec work_flow_client_container cat /app/dist/env-config.js
```

## 完整的构建流程

```bash
# 1. 进入项目目录
cd /data/chenzhixu/WorkFlow

# 2. 确认文件结构
ls -la deploy/
# 应该看到：Dockerfile, start.sh, work_flow_client.yml 等

# 3. 使用启动脚本（推荐）
cd deploy
chmod +x start_work_flow_client.sh
./start_work_flow_client.sh develop

# 或者手动构建
cd ..  # 回到项目根目录
docker build -t work_flow_client:latest . -f deploy/Dockerfile --target develop
cd deploy
docker compose -f work_flow_client.yml up -d -V
```

## 验证部署

```bash
# 1. 检查容器状态
docker ps | grep work_flow_client

# 2. 查看日志
docker logs work_flow_client_container

# 3. 测试访问
curl http://localhost:8000

# 4. 检查后端配置
docker exec work_flow_client_container cat /app/dist/env-config.js
# 应该看到：window.FLASK_BACKEND_URL = "http://game_watchman_server:12008";
```
