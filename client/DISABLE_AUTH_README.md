# 禁用鉴权 - 部署说明

## 已修改的文件

1. **src/app.tsx** - 核心鉴权逻辑
   - 移除了 `getInitialState` 中的登录检查
   - 返回模拟的 Guest User 数据（具有管理员权限）
   - 禁用了 `onPageChange` 中的登录重定向

2. **src/components/RightContent/AvatarDropdown.tsx** - 退出登录
   - 禁用了登出功能的重定向逻辑

## 重新部署步骤

### 在 Linux/WSL 环境中执行：

```bash
# 进入项目目录
cd /path/to/WorkFlow

# 1. 停止现有容器
./deploy/start_work_flow_client.sh down

# 2. 重新构建并启动（根据你的环境选择）
# 开发环境（公司）
./deploy/start_work_flow_client.sh develop

# 或者开发环境（家里）
./deploy/start_work_flow_client.sh develop_home

# 或者生产环境
./deploy/start_work_flow_client.sh publish
```

### 验证部署

访问 http://172.28.200.60:8000/ 应该直接显示应用首页（Dashboard），不会再跳转到登录页面。

## 预期行为

- 访问任何页面都不需要登录
- 右上角显示 "Guest User" 头像
- 所有功能都可以正常访问
- 点击"退出登录"不会有任何效果（已禁用）

## 恢复鉴权

如果将来需要恢复鉴权功能，请：
1. 使用 git 恢复这两个文件的原始版本
2. 重新构建 Docker 镜像
