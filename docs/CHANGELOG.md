# 配置系统更新日志

## 更新时间
2026-07-04 15:52

## 更新内容

### 1. 新增 Preonline 分支支持

#### 1.1 P4 路径
新增预发布分支路径：
```
//C7/Release/Preonline/Server/config/
```

#### 1.2 分支类型
API 参数 `branchType` 现在支持三个值：
- `mainline` - 主干开发分支（默认）
- `weekly` - 周版本分支
- `preonline` - 预发布分支（新增）

#### 1.3 代码更新
**文件**: `server/routers/configTool.py`

**修改点**:
1. `build_config_path()` 函数新增 preonline 分支处理逻辑
2. `getConfig()` API 参数校验更新，允许 `branchType='preonline'`

**代码变更**:
```python
def build_config_path(env: str, branch_type: str = 'mainline') -> tuple:
    # ... 省略部分代码
    if branch_type == 'weekly':
        p4_path = f"//C7/Development/Weekly/Server/config/{sub_dir}/{env}.json"
    elif branch_type == 'preonline':  # 新增
        p4_path = f"//C7/Release/Preonline/Server/config/{sub_dir}/{env}.json"
    else:  # mainline
        p4_path = f"//C7/Development/Mainline/Server/config/{sub_dir}/{env}.json"
    # ... 省略部分代码
```

### 2. 强调 namespace 字段的重要性

#### 2.1 namespace 定义
在配置文件的 `common` 块中，`namespace` 是最重要的唯一标识符：

```json
{
  "common": {
    "namespace": "c7_partner",  // 环境唯一标识符
    "logLevel": "info"
  }
}
```

#### 2.2 namespace 的作用

| 作用 | 说明 |
|------|------|
| **环境唯一标识** | 区分不同的运行环境 |
| **新建配置的 Key** | 创建新环境配置时使用的唯一键 |
| **运行时识别** | 服务器进程通过 namespace 识别当前环境 |
| **日志标记** | 日志和监控系统中使用 namespace 作为环境标识 |

#### 2.3 namespace 规范

- ✅ **必须全局唯一**：不同环境的 namespace 不能重复
- ✅ **命名一致性**：通常与配置文件名保持一致
  - 文件：`c7_partner.json` → namespace: `"c7_partner"`
  - 文件：`c7_weekly.json` → namespace: `"c7_weekly"`
- ⚠️ **不可随意修改**：一旦创建，不建议修改（会影响运行中的服务）

### 3. 文档更新列表

#### 3.1 核心文档
| 文档 | 更新内容 |
|------|---------|
| **01_ConfigOverview.md** | 添加 preonline 分支说明；新增 namespace 字段专门章节 |
| **02_ConfigDirectory.md** | 新增 preonline 分支路径映射；详细说明 namespace 的作用和规范 |
| **QuickStart.md** | 更新 API 参数说明；新增 namespace 规则章节 |
| **README.md** | 核心概念中新增 namespace 和分支类型说明 |
| **SUMMARY.md** | 更新功能概述；配置规则中新增 namespace 章节 |

#### 3.2 更新详情

**01_ConfigOverview.md**:
- P4 路径结构中新增 preonline 分支
- 新增"namespace 字段说明"章节，详细说明其作用和规范

**02_ConfigDirectory.md**:
- 路径映射关系表中新增 preonline 分支
- 分支配置章节新增 7.3 Preonline 分支说明
- 环境配置文件章节新增"关键字段 - namespace"说明

**QuickStart.md**:
- API 参数说明中更新 branchType 支持的值
- 配置系统规则中新增"规则1: namespace 唯一标识"

**README.md**:
- 核心概念中新增"1. namespace 唯一标识"章节
- 新增"5. 分支类型"章节

**SUMMARY.md**:
- API 接口说明中添加分支和 namespace 相关信息
- 配置系统规则中新增"0. namespace 唯一标识"章节
- 新增"5. 分支类型"章节

### 4. API 使用示例

#### 4.1 使用 preonline 分支

```bash
# 获取 preonline 分支的配置
curl "http://localhost:5000/getConfig?env=c7_online&branchType=preonline&syncP4=true"
```

#### 4.2 验证 namespace

**配置文件** (`c7_partner.json`):
```json
{
  "parent": "conf_linux.json",
  "common": {
    "namespace": "c7_partner",  // ✅ 必须与文件名一致
    "logLevel": "info"
  }
}
```

**API 响应**:
```json
{
  "env": "c7_partner",
  "data": {
    "namespace": "c7_partner",  // namespace 字段在返回结果中
    "logLevel": "info",
    ...
  }
}
```

### 5. 向后兼容性

本次更新完全向后兼容：
- ✅ 现有的 `mainline` 和 `weekly` 分支功能不受影响
- ✅ namespace 字段在之前的配置中已存在，只是强调其重要性
- ✅ API 默认行为不变（默认使用 `mainline` 分支）

### 6. 最佳实践

#### 6.1 新建配置文件

创建新环境配置时，确保：

1. **文件名与 namespace 一致**
   ```
   文件名: c7_new_env.json
   namespace: "c7_new_env"
   ```

2. **namespace 全局唯一**
   - 检查现有配置，避免重复
   - 使用有意义的名称

3. **选择合适的分支**
   - 开发阶段：使用 `mainline`
   - 测试阶段：使用 `weekly`
   - 预发布：使用 `preonline`

#### 6.2 分支使用建议

| 分支 | 适用场景 | P4 路径 |
|------|---------|---------|
| **mainline** | 日常开发、功能测试 | `//C7/Development/Mainline/Server/config/` |
| **weekly** | 周版本集成测试 | `//C7/Development/Weekly/Server/config/` |
| **preonline** | 预发布验证、灰度测试 | `//C7/Release/Preonline/Server/config/` |

### 7. 注意事项

1. **namespace 修改风险**
   - ⚠️ 修改运行中环境的 namespace 会导致服务无法识别配置
   - ⚠️ 建议创建新配置而不是修改 namespace

2. **分支选择**
   - preonline 分支通常与生产环境配置高度一致
   - 测试时应确保在正确的分支下获取配置

3. **缓存清理**
   - 切换分支后建议清理缓存：
     ```bash
     curl -X POST "http://localhost:5000/clearConfigCache?env=c7_partner"
     ```

## 测试建议

### 测试 preonline 分支
```bash
# 1. 测试 preonline 分支获取配置
curl "http://localhost:5000/getConfig?env=c7_partner&branchType=preonline&syncP4=true"

# 2. 验证返回的 P4 路径
# 期望: "configP4Path": "//C7/Release/Preonline/Server/config/production/c7_partner.json"

# 3. 测试无效分支类型
curl "http://localhost:5000/getConfig?env=c7_partner&branchType=invalid"
# 期望: HTTP 400, 错误信息提示允许的值
```

### 验证 namespace
```bash
# 1. 获取配置并检查 namespace 字段
curl "http://localhost:5000/getConfig?env=c7_partner" | jq '.data.namespace'
# 期望: "c7_partner"

# 2. 验证不同环境的 namespace 唯一性
curl "http://localhost:5000/getConfig?env=c7_weekly" | jq '.data.namespace'
# 期望: "c7_weekly"
```

## 相关链接

- 代码实现: `server/routers/configTool.py`
- 文档目录: `docs/config/`
- 主要文档: `docs/config/README.md`
- 快速指南: `docs/config/QuickStart.md`
