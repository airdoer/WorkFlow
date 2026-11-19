---
name: workflow-deploy
description: 当用户修改了前端或后端代码后，需要将本地代码同步到远端开发服务器并重启服务时触发本 Skill。触发词："部署"、"deploy"、"发送到远端"、"同步代码"、"重启服务"、"更新远端"、"推送代码到服务器"、"修改后自动部署"。覆盖 SCP 文件传输、容器重启/重建全流程，确保本地代码与远端一致。
version: 1.0.0
---

# WorkFlow 远端部署 Skill

本 Skill 确保本地修改的代码同步到远端开发服务器，解决"本地改了但远端没更新"的问题。

## 服务器与访问配置

| 配置项 | 值 |
|--------|---|
| 服务器地址 | `172.28.200.60` |
| SSH 用户 | `chenzhixu` |
| SSH 密钥 | `C:\Users\Administrator\.ssh\id_rsa` |
| 远端项目路径 | `/data/chenzhixu/WorkFlow` |
| 客户端容器 | `work_flow_client_dev` |
| 服务端容器 | `work_flow_server_container` |

---

## 核心原则

> **每次修改代码后，必须同步到远端并重启对应服务，否则远端运行的是旧代码。**

---

## 部署决策流程

### 判断：需要 Restart 还是 Rebuild？

| 修改内容 | 操作 | 原因 |
|----------|------|------|
| 前端 `.tsx/.ts/.css` 等源码 | **SCP + Restart 客户端** | 客户端容器用 volume 挂载，代码覆盖后 restart 即可 |
| 后端 `.py` 源码 | **SCP + Restart 服务端** | Python 代码覆盖后 restart 即可 |
| `package.json` / `package-lock.json` | **SCP + Rebuild 客户端镜像** | 依赖变更需要重新 npm install |
| `requirements.txt` | **SCP + Rebuild 服务端镜像** | Python 依赖变更需要重新 pip install |
| `Dockerfile` | **Rebuild 对应镜像** | 镜像构建配置变更 |
| `docker-compose.yml` | **Rebuild + 重新创建容器** | 容器配置变更 |
| `server/entrypoint.sh` | **SCP + Restart 服务端** | 入口脚本被 volume 覆盖或需要 rebuild |

---

## 部署操作

### 1. SCP 传输文件到远端

#### 单文件传输

```bash
"C:\Windows\System32\OpenSSH\scp.exe" -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no "<本地路径>" chenzhixu@172.28.200.60:<远端路径>
```

#### 前端文件示例

```bash
# 前端源码 — 远端路径前缀: /data/chenzhixu/WorkFlow/client/src/
scp -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no ^
  "d:\Code\github\WorkFlow\client\src\components\workflow\PropertyPanel.tsx" ^
  chenzhixu@172.28.200.60:/data/chenzhixu/WorkFlow/client/src/components/workflow/PropertyPanel.tsx
```

#### 后端文件示例

```bash
# 后端源码 — 远端路径前缀: /data/chenzhixu/WorkFlow/server/
scp -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no ^
  "d:\Code\github\WorkFlow\server\Implement\workflowImpl\excelExecutor.py" ^
  chenzhixu@172.28.200.60:/data/chenzhixu/WorkFlow/server/Implement/workflowImpl/excelExecutor.py
```

#### 批量传输多个文件

用 `&&` 连接多个 scp 命令：

```bash
scp -i ... file1 remote:path1 && scp -i ... file2 remote:path2 && scp -i ... file3 remote:path3
```

> **本地→远端路径映射规则**：`d:\Code\github\WorkFlow\<相对路径>` → `/data/chenzhixu/WorkFlow/<相对路径>`

---

### 2. 重启容器（普通代码变更）

```bash
# 重启前端
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 "sudo docker restart work_flow_client_dev"

# 重启后端
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 "sudo docker restart work_flow_server_container"
```

---

### 3. 重建镜像（依赖/配置变更）

#### 前端 Rebuild

```bash
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 ^
  "cd /data/chenzhixu/WorkFlow/client/deploy && sudo docker compose build && sudo docker compose up -d"
```

#### 后端 Rebuild

```bash
ssh -i "C:\Users\Administrator\.ssh\id_rsa" -o StrictHostKeyChecking=no chenzhixu@172.28.200.60 ^
  "cd /data/chenzhixu/WorkFlow/server && sudo docker compose -f work_flow_server.yml build && sudo docker compose -f work_flow_server.yml up -d"
```

---

### 4. 等待服务就绪

```bash
# 等待前端就绪（~15秒）
ssh ... "sleep 15 && sudo docker logs --tail=3 work_flow_client_dev 2>&1"
# 看到 "➜ Local: http://localhost:8000" 即表示就绪

# 等待后端就绪
ssh ... "sleep 10 && sudo docker logs --tail=5 work_flow_server_container 2>&1"
# 看到 Flask/Gunicorn 启动日志即表示就绪
```

---

## 完整部署流程（推荐）

每次修改代码后，按以下顺序执行：

```
1. 修改本地代码
2. SCP 传输修改的文件到远端（路径保持一致）
3. 判断是否需要 rebuild（仅依赖/配置变更需要）
4. Restart 对应容器（或 Rebuild 镜像）
5. 等待服务就绪
6. 在浏览器验证 http://172.28.200.60:8000
```

---

## 常见问题

### Q: 修改了代码但远端表现没变？

1. 确认 SCP 是否成功传输（检查 scp 输出是否有 `100%` 字样）
2. 确认是否 restart 了对应容器
3. 前端修改 `.tsx` 后 Vite HMR 通常会自动更新，但也可能需要 restart
4. 浏览器可能有缓存，尝试 Ctrl+Shift+R 强制刷新

### Q: 前端修改后容器退出？

1. 检查语法错误：`sudo docker logs --tail=20 work_flow_client_dev`
2. 如果有 TypeScript 编译错误，修复后重新 SCP + restart

### Q: 后端修改后返回 500？

1. 检查 Python 错误：`sudo docker logs --tail=50 work_flow_server_container`
2. 常见原因：缩进错误、import 缺失、try/except 结构错误

---

## 远端别名参考（czx.bashrc）

| 别名 | 等效命令 | 用途 |
|------|---------|------|
| `gotoworkflow` | `cd /data/chenzhixu/WorkFlow` | 进入项目目录 |
| `restartworkflowclient` | `docker restart work_flow_client_dev` | 重启前端 |
| `restartworkflowserver` | `docker restart work_flow_server_container` | 重启后端 |
