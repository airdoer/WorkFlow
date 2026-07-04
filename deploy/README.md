# WorkFlow Client Docker 部署

## 📁 文件说明

```
deploy/
├── Dockerfile                    # Docker 镜像构建文件（dev-hot-reload 阶段）
├── docker-compose.yml           # Docker Compose 配置（开发环境）
├── start_work_flow_client.sh    # Linux/Mac 启动脚本
├── start_work_flow_client.bat   # Windows 启动脚本
└── README.md                    # 本文件
```

## 🚀 快速开始

### Windows 用户
```bash
cd deploy
start_work_flow_client.bat
```

### Linux/Mac 用户
```bash
cd deploy
chmod +x start_work_flow_client.sh
./start_work_flow_client.sh
```

## 📋 常用命令

### 启动服务
```bash
# Windows
start_work_flow_client.bat

# Linux/Mac
./start_work_flow_client.sh
```

### 查看日志
```bash
# Windows
start_work_flow_client.bat logs

# Linux/Mac
./start_work_flow_client.sh logs
```

### 重启服务
```bash
# Windows
start_work_flow_client.bat restart

# Linux/Mac
./start_work_flow_client.sh restart
```

### 停止服务
```bash
# Windows
start_work_flow_client.bat down

# Linux/Mac
./start_work_flow_client.sh down
```

## 💡 特性

### ✅ 热更新支持
- 修改宿主机源代码后自动同步到容器
- Umi 开发服务器自动检测变更并热更新
- 浏览器自动刷新，无需手动重启

### ✅ Volume 映射
```yaml
volumes:
  - ..:/app              # 映射项目根目录
  - /app/node_modules    # 排除 node_modules（使用容器内的）
```

### ✅ 自动重启
容器配置了 `restart: unless-stopped`，Docker 重启后自动恢复

## 🔧 技术细节

### Docker 多阶段构建
```dockerfile
FROM node:22 AS dev-hot-reload
# 只安装依赖，源代码通过 volume 挂载
```

### 端口映射
- 容器端口：8000
- 宿主机端口：8000
- 访问地址：http://localhost:8000

### 网络配置
- 使用外部网络 `redis-network`
- 可与其他服务通信

## 🐛 故障排查

### 问题1：端口被占用
```bash
# 查看占用端口 8000 的进程
netstat -ano | findstr :8000  # Windows
lsof -i :8000                 # Linux/Mac

# 停止旧容器
./start_work_flow_client.sh down
```

### 问题2：热更新不生效
```bash
# 重新构建镜像
cd deploy
docker-compose -f docker-compose.yml up -d --build
```

### 问题3：依赖安装失败
```bash
# 清理并重新构建
docker-compose -f docker-compose.yml down
docker rmi work_flow_client:dev
./start_work_flow_client.sh
```

### 问题4：查看容器内部
```bash
# 进入容器
docker exec -it work_flow_client_dev bash

# 查看文件
ls -la /app

# 查看进程
ps aux
```

## 📊 与宿主机开发对比

| 特性 | 宿主机开发 | Docker 开发 |
|------|-----------|------------|
| 环境隔离 | ❌ | ✅ |
| 依赖管理 | 需要本地安装 | 容器内独立 |
| 热更新 | ✅ | ✅ |
| 部署一致性 | ❌ | ✅ |
| 多项目切换 | 麻烦 | 简单 |

## 🎯 使用建议

1. **日常开发**：使用这个配置，支持热更新
2. **团队协作**：统一 Docker 环境，避免"我这能跑"问题
3. **快速上手**：新成员只需运行启动脚本即可

## 📝 注意事项

1. **node_modules 不同步**：容器使用自己的 node_modules，避免跨平台兼容性问题
2. **代理配置**：Dockerfile 中配置了内网代理，外网使用需要修改
3. **文件权限**：Linux/Mac 需要给 .sh 文件添加执行权限
