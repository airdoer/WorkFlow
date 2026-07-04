# WorkFlow Client Docker 部署指南

## 概述

WorkFlow Client 是基于 Umi Max (Ant Design Pro) 的前端项目，通过 Docker 容器化部署。镜像构建完成后，使用 `npm run preview` 启动静态预览服务，监听 8000 端口。

## 文件结构

```
deploy/
├── Dockerfile                  # 多阶段构建定义（develop / develop_home / publish）
├── build_with_proxy.sh         # 公司内网代理构建脚本
├── start_work_flow_client.sh   # 一键构建+启动脚本
├── start.sh                    # 容器内启动脚本
└── work_flow_client.yml        # docker-compose 配置
```

## 构建与启动

### 方式一：内网代理构建

```bash
bash deploy/build_with_proxy.sh
```

该脚本会设置内网代理环境变量，然后从项目根目录执行 `docker build`，目标阶段为 `develop`。

### 方式二：一键构建+启动

```bash
# 默认 develop 模式
bash deploy/start_work_flow_client.sh

# 指定模式
bash deploy/start_work_flow_client.sh publish
bash deploy/start_work_flow_client.sh develop_home

# 停止容器
bash deploy/start_work_flow_client.sh down
```

该脚本会先构建镜像，再通过 docker-compose 启动容器。

### 方式三：手动操作

```bash
# 构建
docker build -t work_flow_client:latest . --target develop -f deploy/Dockerfile

# 启动
cd deploy && docker-compose -f work_flow_client.yml up -d -V
```

## 构建阶段说明

| 阶段 | 说明 |
|------|------|
| `develop` | 开发环境镜像，含内网代理配置 |
| `develop_home` | 开发环境镜像（无代理），适用于外网环境 |
| `publish` | 生产运行镜像，含内网代理配置 |

通过 `--target` 参数选择构建阶段：

```bash
docker build -t work_flow_client:latest . --target publish -f deploy/Dockerfile
```

## 容器启动流程

容器启动时执行 `/app/start.sh`：

1. 创建 `/app/dist` 目录
2. 根据 `FLASK_BACKEND_URL` 环境变量生成 `env-config.js`
3. 执行 `npm run preview` 启动预览服务

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `FLASK_BACKEND_URL` | 后端服务地址 | `http://game_watchman_server:12008` |

## 踩坑记录

以下是在实际部署过程中遇到的问题及解决方案，后续开发和迭代时需注意。

### 1. `.dockerignore` 排除了构建必需的文件

**现象**：构建时报 `Module not found: Can't resolve '@root/docs/cheatsheet.en-US.md'`

**原因**：`.dockerignore` 中的 `docs` 和 `*.md` 规则将 `docs/cheatsheet.*.md` 文件排除在 Docker 构建上下文之外，导致容器内找不到这些文件。Umi 的 alias 配置 `@root -> 项目根目录`，`Welcome.tsx` 中通过 `@root/docs/cheatsheet.*.md` 引用了这些文件。

**解决**：

- 不能直接排除整个 `docs` 目录后再用 `!docs/cheatsheet.*.md` 重新包含，因为 Docker 的 `.dockerignore` 规则中，**父目录被排除后，无法用 `!` 重新包含其子文件**（这是 Docker 的已知行为）
- 正确做法是：只排除不需要的子目录（如 `docs/roadmap`），不排除整个 `docs` 目录
- 对于 `*.md` 通配规则，用 `!docs/cheatsheet.en-US.md` 和 `!docs/cheatsheet.zh-CN.md` 进行例外处理

**经验**：编写 `.dockerignore` 时，需要确认项目中所有被代码引用的文件（包括通过 alias 引用的非 src 目录文件）都不会被排除。

### 2. `.dockerignore` 排除了 mock 目录导致容器启动崩溃

**现象**：容器启动后立即退出，日志报 `Cannot find module '../../../../mock/utils'`

**原因**：`.dockerignore` 中排除了 `mock` 目录，但 `npm run preview` (umi preview) 会加载 mock 数据，`src/pages/account/center/_mock.ts` 引用了 `mock/utils.ts`。

**解决**：从 `.dockerignore` 中移除 `mock` 行，使 mock 目录包含在构建上下文中。

**经验**：umi 的 preview 模式依赖 mock 数据，即使生产构建也需要 mock 目录。如果确实想排除 mock，需要在 `config/config.ts` 的 `mock` 配置中排除对应文件。

### 3. docker-compose volumes 挂载覆盖了镜像内容

**现象**：容器启动报 `npm error enoent Could not read package.json: Error: ENOENT: no such file or directory, open '/app/package.json'`

**原因**：`work_flow_client.yml` 中配置了 `volumes: - .:/app`，将 deploy 目录（仅含几个脚本文件）挂载到了容器的 `/app` 工作目录，覆盖了镜像中的完整项目文件。

**解决**：移除 `volumes` 挂载配置。当前部署使用的是构建好的镜像，不需要挂载宿主机目录。

**经验**：docker-compose 中 `volumes: - .:/app` 仅适合开发模式热更新场景。对于生产/预览部署，不应挂载宿主机目录覆盖镜像内容。如果未来需要开发模式热更新，应该挂载项目根目录而非 deploy 目录，并配合 `node_modules` 匿名卷避免冲突。

### 4. Docker 构建缓存导致修改未生效

**现象**：修改了 `.dockerignore` 后重新构建，仍然报同样的错误

**原因**：Docker 的层缓存机制使得 `COPY . .` 步骤使用了旧的缓存层（当时 docs 目录未复制进去），即使 `.dockerignore` 已修改，如果上下文的 hash 未变化，Docker 仍会使用缓存。

**解决**：使用 `--no-cache` 参数强制重新构建。

```bash
docker build --no-cache -t work_flow_client:latest . --target develop -f deploy/Dockerfile
```

**经验**：修改 `.dockerignore` 后，必须加 `--no-cache` 或删除旧镜像后重新构建，否则 Docker 可能使用过期的缓存层。

## 当前 `.dockerignore` 配置

```
node_modules
dist
.git
.github
.vscode
.husky
*.log
*.md
!README.md
!docs/cheatsheet.en-US.md
!docs/cheatsheet.zh-CN.md
.env*
coverage
.cache
.temp
.DS_Store
tests
docs/roadmap
```

要点：
- `docs/` 目录不整体排除，仅排除 `docs/roadmap` 子目录
- `*.md` 排除所有 markdown 文件，但用 `!` 保留构建必需的 cheatsheet 文件
- `mock/` 目录不排除，preview 模式依赖 mock 数据
- `tests` 目录不影响构建和运行，可排除

## 当前 `work_flow_client.yml` 配置

```yaml
version: '3.7'
services:
  work_flow_client:
    image: work_flow_client:latest
    container_name: work_flow_client_container
    ports:
      - "8000:8000"
    environment:
      - FLASK_BACKEND_URL=http://game_watchman_server:12008
    networks:
      - redis-network

networks:
  redis-network:
    external: true
```

要点：
- 不挂载 volumes，使用镜像内完整构建产物
- 通过 `FLASK_BACKEND_URL` 环境变量配置后端地址
- 使用外部 `redis-network` 网络与其他服务通信

## 新增文件/目录时的检查清单

当项目新增文件或目录时，需确认以下事项：

1. 新文件是否被代码 import 引用？如果是，确认 `.dockerignore` 未排除该文件
2. 新目录是否被整体排除在 `.dockerignore` 中？如果是，检查其子文件是否被构建所需
3. 新增 mock 文件？确认 mock 目录在构建上下文中
4. 修改了 `.dockerignore`？重新构建时加 `--no-cache`
5. 修改了 alias 路径（如 `@root`）？确认对应文件在容器内可达
