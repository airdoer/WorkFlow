---
name: workflow-debug
description: This skill should be used when the user asks to "debug WorkFlow", "test WorkFlow", "check WorkFlow server", "connect to WorkFlow remote", "查看容器日志", "重启容器", "测试接口", "SSH连接服务器", "调试WorkFlow", "检查服务状态", or needs to SSH into the WorkFlow development server at 172.28.200.60, inspect Docker containers, run backend/frontend tests, or verify API endpoints. Covers SSH connection, Docker container management, log inspection, and API testing for the WorkFlow project.
version: 1.0.0
---

# WorkFlow 调试与测试 Skill

本 Skill 提供对 WorkFlow 项目远程开发服务器的调试和测试操作指南。

## 服务器与访问配置

| 配置项 | 值 |
|--------|---|
| 服务器地址 | `172.28.200.60` |
| SSH 用户 | `chenzhixu` |
| SSH 端口 | `22` |
| SSH 密钥 | `C:\Users\Administrator\.ssh\id_rsa` |
| 项目路径 | `/data/chenzhixu/WorkFlow` |
| 客户端容器 | `work_flow_client_dev` |
| 服务端容器 | `work_flow_server_container` |
| **前端访问地址** | `http://172.28.200.60:8000/workflow/fullscreen?id=2caab557-41a2-4a41-a274-f2325c86160d` |
| **后端访问地址** | `http://172.28.200.60:16666` |

---

## 1. SSH 连接服务器

```bash
ssh -i "C:\Users\Administrator\.ssh\id_rsa" chenzhixu@172.28.200.60
```

加 `-o StrictHostKeyChecking=no` 可跳过首次 host key 确认（适合脚本）：

```bash
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60
```

---

## 2. 前端访问与测试

### 2.1 直接访问前端页面

```
http://172.28.200.60:8000/workflow/fullscreen?id=8e9bfca2-5826-4e27-8fb9-591f1a681f75
```

### 2.2 测试前端是否正常响应

```bash
# 本地 curl 检测前端是否可访问
curl -s -o /dev/null -w "%{http_code}" "http://172.28.200.60:8000/workflow/fullscreen?id=2caab557-41a2-4a41-a274-f2325c86160d"
```

返回 `200` 表示正常，`502`/`503` 说明前端容器异常。

---

## 3. 后端 API 测试

后端基础地址：`http://172.28.200.60:16666`

### 3.1 健康检查

```bash
# 测试后端是否存活
curl -s http://172.28.200.60:16666/health
curl -s http://172.28.200.60:16666/
```

### 3.2 常用接口测试示例

```bash
# GET 请求示例
curl -s http://172.28.200.60:16666/<接口路径>

# POST 请求示例（JSON）
curl -s -X POST http://172.28.200.60:16666/<接口路径> \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'

# 带认证 Token
curl -s http://172.28.200.60:16666/<接口路径> \
  -H "Authorization: Bearer <token>"
```

### 3.3 在服务器容器内测试后端（排查网络问题）

```bash
# 在服务端容器内部访问自身
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 \
  "docker exec work_flow_server_container curl -s http://localhost:<内部端口>/health"
```

---

## 4. telnet 连接

### 4.1 端口
telnet的端口是本地的6666
在连接ssh后，可以通过telnet localhost 6666来进行连接

### 4.2

本质上是一个python console，可以通过import g等来进行调试
相关的实现代码可以查看server\tools\TelnetHandler.py


## 5. Docker 容器管理

### 5.1 查看容器状态

```bash
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 "docker ps | grep work_flow"

# 查看包含已停止的容器
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 "docker ps -a | grep work_flow"
```

### 5.2 查看端口映射

```bash
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 \
  "docker port work_flow_server_container && docker port work_flow_client_dev"
```

### 5.3 查看容器日志

```bash
# 服务端日志（最新 100 行）
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 \
  "docker logs --tail=100 work_flow_server_container"

# 实时跟踪服务端日志
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 \
  "docker logs -f work_flow_server_container"

# 客户端日志（最新 100 行）
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 \
  "docker logs --tail=100 work_flow_client_dev"

# 实时跟踪客户端日志
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 \
  "docker logs -f work_flow_client_dev"
```

### 5.4 重启容器

```bash
# 重启服务端
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 \
  "docker restart work_flow_server_container"

# 重启客户端
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 \
  "docker restart work_flow_client_dev"

# 重启全部
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 \
  "docker restart work_flow_server_container work_flow_client_dev"
```

### 4.5 进入容器 Shell（交互式调试）

```bash
# 进入服务端容器
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 -t \
  "docker exec -it work_flow_server_container bash"

# 进入客户端容器
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 -t \
  "docker exec -it work_flow_client_dev bash"
```

---

## 6. 项目代码操作

```bash
# 查看项目目录
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 \
  "ls -la /data/chenzhixu/WorkFlow"

# 查看 git 状态
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 \
  "cd /data/chenzhixu/WorkFlow && git status"

# 拉取最新代码
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 \
  "cd /data/chenzhixu/WorkFlow && git pull"

# 拉取代码并重启容器
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 \
  "cd /data/chenzhixu/WorkFlow && git pull && docker restart work_flow_server_container work_flow_client_dev"
```

---

## 7. 常见调试场景

### 场景 A：后端接口 502 / 无响应

1. 检查容器是否在运行：`docker ps | grep work_flow_server`
2. 查看服务端日志排查错误：`docker logs --tail=100 work_flow_server_container`
3. 尝试重启服务端：`docker restart work_flow_server_container`
4. 重启后再次测试：`curl -s http://172.28.200.60:16666/health`

### 场景 B：前端页面无法访问（端口 8000）

1. 检查客户端容器状态：`docker ps | grep work_flow_client`
2. 查看客户端日志：`docker logs --tail=100 work_flow_client_dev`
3. 检查端口映射：`docker port work_flow_client_dev`
4. 重启客户端：`docker restart work_flow_client_dev`
5. 重新访问：`http://172.28.200.60:8000/workflow/fullscreen?id=2caab557-41a2-4a41-a274-f2325c86160d`

### 场景 C：代码更新后服务不生效

```bash
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 \
  "cd /data/chenzhixu/WorkFlow && git pull && docker restart work_flow_server_container work_flow_client_dev"
```

### 场景 D：全面健康检查

```bash
# 一次性检查容器状态 + 后端健康 + 前端可达
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 \
  "echo '=== 容器状态 ===' && docker ps | grep work_flow && echo '=== 后端测试 ===' && curl -s -o /dev/null -w 'HTTP %{http_code}' http://localhost:16666/ && echo ''"
```

---

## 8. 快速参考

```bash
# SSH 连接
ssh -i "C:\Users\Administrator\.ssh\id_rsa" chenzhixu@172.28.200.60

# 前端地址
http://172.28.200.60:8000/workflow/fullscreen?id=2caab557-41a2-4a41-a274-f2325c86160d

# 后端地址
http://172.28.200.60:16666

# 查服务端日志
业务优先用
less /data/chenzhixu/WorkFlow/server/log/work_flow_server.log
容器启动失败用
docker logs -f work_flow_server_container

# 查客户端日志
docker logs -f work_flow_client_dev

# 重启全部容器
docker restart work_flow_server_container work_flow_client_dev

# 项目路径
cd /data/chenzhixu/WorkFlow
```
