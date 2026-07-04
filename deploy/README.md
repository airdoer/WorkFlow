# Docker 部署文档

本项目支持通过 Docker 进行部署，所有部署相关文件都在 `deploy` 目录中。

## 文件说明

- `Dockerfile` - Docker 镜像构建文件
- `work_flow_client.yml` - Docker Compose 配置文件
- `start_work_flow_client.sh` - 启动脚本
- `start.sh` - 容器内启动脚本（用于注入环境变量）

## 环境变量配置

### FLASK_BACKEND_URL

项目通过 `FLASK_BACKEND_URL` 环境变量配置后端 API 地址。

**配置方式：**

1. **Docker Compose 方式（推荐）**
   
   在 `work_flow_client.yml` 中配置：
   ```yaml
   environment:
     - FLASK_BACKEND_URL=http://game_watchman_server:12008
   ```

2. **Docker 命令行方式**
   ```bash
   docker run -e FLASK_BACKEND_URL=http://your-backend:port work_flow_client:latest
   ```

3. **本地开发**
   
   本地开发时，后端地址通过代理配置，无需设置环境变量。

## 构建模式

支持三种构建模式：

- `develop` - 开发环境（带代理）
- `develop_home` - 家庭开发环境（无代理）
- `publish` - 生产环境（带代理）

## 使用方法

### 1. 启动服务

**重要**：脚本会自动处理构建上下文，无需手动切换目录。

```bash
# 方式 1：使用启动脚本（推荐）
cd deploy
chmod +x start_work_flow_client.sh
./start_work_flow_client.sh develop

# 方式 2：使用代理构建脚本（如果网络需要代理）
cd deploy
chmod +x build_with_proxy.sh
./build_with_proxy.sh

# 方式 3：手动构建（从项目根目录）
cd /path/to/WorkFlow  # 项目根目录
docker build -t work_flow_client:latest . --target develop -f deploy/Dockerfile
docker compose -f deploy/work_flow_client.yml up -d -V
```

### 2. 停止服务

```bash
cd deploy
./start_work_flow_client.sh down
```

### 3. 访问应用

启动成功后，访问 http://localhost:8000

## 技术实现

### 后端地址配置原理

1. **代码层面** (`src/app.tsx`)：
   ```typescript
   const getBackendURL = () => {
     // 运行时环境变量（Docker 容器中通过 window 注入）
     if (typeof window !== 'undefined' && (window as any).FLASK_BACKEND_URL) {
       return (window as any).FLASK_BACKEND_URL;
     }
     // 构建时环境变量
     if (process.env.FLASK_BACKEND_URL) {
       return process.env.FLASK_BACKEND_URL;
     }
     // 默认值
     return isDev ? '' : 'https://pro-api.ant-design-demo.workers.dev';
   };
   ```

2. **启动脚本** (`deploy/start.sh`)：
   - 容器启动时，将环境变量写入 `env-config.js` 文件
   - 该文件在 HTML 中被引入，将环境变量注入到 `window` 对象

3. **构建配置** (`config/config.ts`)：
   - 在生产环境构建时自动引入 `env-config.js`

## 网络配置

项目使用 `redis-cluster-network` 外部网络，确保该网络已创建：

```bash
docker network create redis-cluster-network
```

## 端口说明

- 容器内端口：8000
- 宿主机端口：8000
- 后端端口：12008（可通过环境变量修改）

## 注意事项

1. 首次构建可能需要较长时间，请耐心等待
2. 确保 Docker 网络 `redis-cluster-network` 已创建
3. 修改后端地址后需要重启容器才能生效
4. 开发环境使用了公司代理，家庭环境请使用 `develop_home` 模式
