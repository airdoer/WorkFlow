---
name: workflow-commit
description: 当用户说"提交代码"、"commit"、"git commit"、"提交到main"、"推送到远程"、"push代码"、"保存改动"、"git提交"、"提交工作流"时触发本 Skill。提供规范化 Git 提交工作流，自动生成中文 commit message，提交到 main 分支并推送到远程仓库。覆盖 git add、git commit、git push 全流程。
version: 1.0.0
---

# WorkFlow Git 提交 Skill

本 Skill 提供规范的 Git 提交工作流，确保代码变更以中文描述提交到 `main` 分支并推送到远程仓库。

## 仓库配置

| 配置项 | 值 |
|--------|---|
| 远程仓库名 | `origin` |
| 主分支 | `main` |
| 项目根目录 | WorkFlow 项目根目录 |

---

## 提交工作流

### Step 1: 检查变更状态

```bash
git status
git diff --stat
```

确认有哪些文件被修改，判断变更范围。

---

### Step 2: 暂存所有变更

```bash
git add -A
```

> 如果用户只想暂存特定文件，则用 `git add <file1> <file2> ...`

---

### Step 3: 生成中文 Commit Message

**必须遵循 Conventional Commits 规范，且描述使用中文：**

格式：
```
<type>(<scope>): <中文描述>
```

#### Type 规范

| Type | 含义 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(excel): 新增多sheet标签页切换功能` |
| `fix` | 修复 Bug | `fix(node): 修复节点选择边框不显示的问题` |
| `refactor` | 重构（不改变功能） | `refactor(render): 重构Univer渲染逻辑，分离compact和full模式` |
| `style` | 样式调整 | `style(panel): 调整属性面板表格高度和间距` |
| `docs` | 文档变更 | `docs(readme): 更新项目部署文档` |
| `chore` | 构建/工具变更 | `chore(deps): 升级依赖版本` |
| `perf` | 性能优化 | `perf(render): 优化大表格渲染性能，移除maxRows截断` |
| `test` | 测试相关 | `test(api): 添加节点运行接口测试` |

#### 额外要求

1. **描述必须使用中文**，清晰说明"做了什么"
2. **描述基于最近修改内容生成**，不要凭空编造
3. 如果一次提交涉及多个改动，用 `·` 分隔描述，例如：
   ```
   feat(excel): 支持多sheet展示 · 修复二进制内容乱码显示 · 统一节点卡片和属性面板样式
   ```
4. **Body 可选**，仅在变更复杂时添加，同样使用中文

---

### Step 4: 提交到 main 分支

```bash
git commit -m "<type>(<scope>): <中文描述>"
```

如果有多行描述（含 Body），使用：

```bash
git commit -m "<type>(<scope>): <中文描述>" -m "<详细说明>" -m "<补充信息>"
```

> **注意**：在 Windows cmd 中，commit message 不要使用换行符和特殊字符（如引号嵌套），保持单行最佳。

---

### Step 5: 推送到远程 main 分支

```bash
git push origin main
```

> 如果当前分支是 `master` 而非 `main`，使用 `git push origin master`。
> 先用 `git branch --show-current` 确认当前分支名。

---

## 完整流程示例

```bash
# 1. 查看变更
git status
git diff --stat

# 2. 暂存
git add -A

# 3. 提交（中文描述，Conventional Commits 格式）
git commit -m "feat(excel): 去掉节点卡片重复表格 · 增加表格滚动支持 · 属性面板使用完整Univer渲染"

# 4. 推送
git push origin main
```

---

## 注意事项

1. **永远不要 force push**（`--force`），除非用户明确要求
2. **提交前检查** `git diff --cached --stat`，确保暂存的变更符合预期
3. **当前分支确认**：本项目主分支可能是 `main` 或 `master`，提交前用 `git branch --show-current` 确认
4. **Windows 环境**：所有命令在 `cmd.exe` 中执行，注意路径使用反斜杠，长命令考虑写脚本文件
5. **冲突处理**：如果 push 失败提示冲突，先 `git pull origin main --rebase`，解决冲突后再 push
6. **message 中的中文**：Windows cmd 对中文 commit message 支持良好，无需额外编码设置
7. **提交后部署**：代码 push 后远端服务器并不会自动更新，需要加载 `workflow-deploy` skill 将修改同步到远端并重启服务
