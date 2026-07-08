# C7 配置工具快速使用指南

## 功能概述

C7 配置工具提供了一套完整的配置管理系统，支持：
- ✅ 配置文件的继承和合并
- ✅ 从 P4 自动同步配置
- ✅ 提取指定进程的配置
- ✅ 智能缓存机制
- ✅ 完整的错误处理

## API 接口

### 1. 获取配置 - `/getConfig`

#### 1.1 获取完整环境配置

**请求**:
```http
GET /getConfig?env=c7_partner&syncP4=false
```

**参数**:
- `env` **(必选)**: 环境名称，如 `c7_partner`, `c7_weekly`, `c7_dev_weekly`
- `syncP4` **(可选)**: 是否强制从 P4 同步，默认 `false`
- `branchType` **(可选)**: 分支类型，`mainline`、`weekly` 或 `preonline`，默认 `mainline`

**响应示例**:
```json
{
  "env": "c7_partner",
  "branchType": "mainline",
  "configP4Path": "//C7/Development/Mainline/Server/config/production/c7_partner.json",
  "configP4PathAtCL": "//C7/Development/Mainline/Server/config/production/c7_partner.json@12345",
  "configChangelist": 12345,
  "data": {
    "common": {
      "namespace": "c7_partner",
      "logLevel": "info",
      "serverZoneId": 217
    },
    "logic": {
      "lua_call_timeout": 5000,
      "database": "c7_partner"
    },
    "logic_1": {
      "ip": "inner_ip1",
      "console": {"ip": "127.0.0.1", "port": 7601}
    }
  }
}
```

---

#### 1.2 获取指定进程配置

**请求**:
```http
GET /getConfig?env=c7_partner&processType=logic&processId=1&syncP4=false
```

**参数**:
- `env` **(必选)**: 环境名称
- `processType` **(必选)**: 进程类型，如 `logic`, `dbmgr`, `router`, `cluster_manager`
- `processId` **(可选)**: 进程实例ID，如 `1`, `2`, `3`
- `syncP4` **(可选)**: 是否强制同步
- `branchType` **(可选)**: 分支类型

**响应示例**:
```json
{
  "env": "c7_partner",
  "branchType": "mainline",
  "processType": "logic",
  "processId": 1,
  "configP4Path": "//C7/Development/Mainline/Server/config/production/c7_partner.json",
  "configChangelist": 12345,
  "data": {
    "namespace": "c7_partner",
    "logLevel": "info",
    "serverZoneId": 217,
    "lua_call_timeout": 5000,
    "database": "c7_partner",
    "ip": "inner_ip1",
    "console": {
      "ip": "127.0.0.1",
      "port": 7601
    },
    "metrics": {
      "host": "0.0.0.0",
      "port": 9104
    }
  }
}
```

**说明**: 返回的配置是 `common` + `logic` + `logic_1` 合并后的结果。

---

### 2. 清除缓存 - `/clearConfigCache`

#### 2.1 清除所有缓存

**请求**:
```http
POST /clearConfigCache
```

**响应**:
```json
{
  "message": "Cleared all 15 cache entries"
}
```

---

#### 2.2 清除指定环境的缓存

**请求**:
```http
POST /clearConfigCache?env=c7_partner
```

**响应**:
```json
{
  "message": "Cleared 5 cache entries",
  "prefix": "config_c7_partner"
}
```

---

#### 2.3 清除指定环境和分支的缓存

**请求**:
```http
POST /clearConfigCache?env=c7_partner&branchType=mainline
```

**响应**:
```json
{
  "message": "Cleared 3 cache entries",
  "prefix": "config_c7_partner_mainline"
}
```

---

## 使用场景

### 场景1: 查看生产环境配置

```bash
curl "http://localhost:5000/getConfig?env=c7_online&syncP4=true"
```

### 场景2: 调试本地开发环境

```bash
# 获取 c7_dev_weekly 的 logic_1 配置
curl "http://localhost:5000/getConfig?env=c7_dev_weekly&processType=logic&processId=1"
```

### 场景3: 对比不同进程的配置

```bash
# logic_1
curl "http://localhost:5000/getConfig?env=c7_partner&processType=logic&processId=1"

# logic_2
curl "http://localhost:5000/getConfig?env=c7_partner&processType=logic&processId=2"
```

### 场景4: 配置更新后刷新缓存

```bash
# 清除缓存
curl -X POST "http://localhost:5000/clearConfigCache?env=c7_partner"

# 强制同步最新配置
curl "http://localhost:5000/getConfig?env=c7_partner&syncP4=true"
```

---

## 错误处理

### 错误1: 环境不存在

**请求**:
```http
GET /getConfig?env=invalid_env
```

**响应** (404):
```json
{
  "errMsg": "Config file not found",
  "p4Path": "//C7/Development/Mainline/Server/config/production/invalid_env.json",
  "localPath": "E:/Project/C7_project/Server/config/production/invalid_env.json",
  "suggestion": "Check if the file exists in P4 or if the environment name is correct"
}
```

---

### 错误2: 循环继承

**响应** (400):
```json
{
  "errMsg": "Circular inheritance detected in config files",
  "inheritanceChain": "file_a.json -> file_b.json -> file_a.json",
  "files": ["file_a.json", "file_b.json"],
  "suggestion": "Remove circular references from the parent fields"
}
```

---

### 错误3: JSON 格式错误

**响应** (400):
```json
{
  "errMsg": "Invalid JSON format in config file",
  "file": "E:/Project/C7_project/Server/config/production/c7_test.json",
  "error": "Expecting ',' delimiter",
  "line": 5,
  "column": 1,
  "suggestion": "Fix JSON syntax errors using a JSON validator"
}
```

---

### 错误4: P4 同步失败

**响应** (500):
```json
{
  "errMsg": "Failed to sync config from P4",
  "p4Path": "//C7/Development/Mainline/Server/config/production/c7_partner.json",
  "error": "Perforce client error: Connection timeout",
  "suggestion": "Check P4 connection, permissions, or file availability"
}
```

---

## 配置系统规则

### 规则1: namespace 唯一标识

每个配置文件必须在 `common` 块中定义唯一的 `namespace`：

```json
{
  "parent": "conf_linux.json",
  "common": {
    "namespace": "c7_test",    // 环境唯一标识，必须全局唯一
    "logLevel": "info"
  }
}
```

**namespace 的重要性**:
- ✅ 环境唯一标识符，用于区分不同环境
- ✅ 新建配置时的唯一 Key
- ✅ 服务器运行时识别当前环境
- ✅ 日志和监控中的环境标记
- ⚠️ 必须全局唯一，不能重复
- ⚠️ 通常与文件名一致（如 `c7_partner.json` → `namespace: "c7_partner"`）

---

### 规则2: parent 继承

配置文件可以通过 `parent` 字段继承另一个配置：

```json
{
  "parent": "conf_linux.json",
  "common": {
    "namespace": "c7_test"
  }
}
```

**继承链**:
```
conf_base.json
    ↓
conf_linux.json
    ↓
c7_test.json
```

---

### 规则3: 合并策略

| 数据类型 | 合并策略 | 示例 |
|---------|---------|------|
| **对象** | 递归合并，子覆盖父 | `{"a": 1}` + `{"b": 2}` = `{"a": 1, "b": 2}` |
| **数组** | 完全替换 | `[1, 2, 3]` + `[4, 5]` = `[4, 5]` |
| **基本类型** | 直接覆盖 | `"value1"` + `"value2"` = `"value2"` |

---

### 规则4: 进程配置优先级

```
common (优先级最低)
    ↓
logic (进程类型)
    ↓
logic_1 (优先级最高)
```

**示例**:
```json
{
  "common": {"logLevel": "warn"},
  "logic": {"logLevel": "info"},
  "logic_1": {"logLevel": "debug"}
}
```

获取 `logic_1` 配置时，最终 `logLevel` 为 `"debug"`。

---

## 常见环境列表

| 环境名称 | 说明 | 目录 |
|---------|------|------|
| `c7_online` | 线上生产环境 | production |
| `c7_weekly` | 周版本测试环境 | production |
| `c7_partner` | 合作伙伴环境 | production |
| `c7_daily` | 日常测试环境 | production |
| `c7_dev_weekly` | 开发周版本 | local |
| `c7_qa1` ~ `c7_qa8` | QA 测试环境 | local |
| `c7_dev` | 本地开发环境 | local |

---

## 性能优化建议

### 1. 使用缓存

默认情况下，配置会被缓存，避免频繁从 P4 同步：

```bash
# 第一次请求：从 P4 同步（慢）
curl "http://localhost:5000/getConfig?env=c7_partner&syncP4=true"

# 后续请求：使用缓存（快）
curl "http://localhost:5000/getConfig?env=c7_partner&syncP4=false"
```

### 2. 仅获取需要的进程配置

如果只需要某个进程的配置，不要获取完整配置：

```bash
# ❌ 不推荐：获取完整配置（包含所有进程）
curl "http://localhost:5000/getConfig?env=c7_partner"

# ✅ 推荐：只获取 logic_1 配置
curl "http://localhost:5000/getConfig?env=c7_partner&processType=logic&processId=1"
```

### 3. 定期清理缓存

在配置文件更新后，记得清理缓存：

```bash
curl -X POST "http://localhost:5000/clearConfigCache?env=c7_partner"
```

---

## 相关文档

如需深入了解配置系统，请阅读以下文档：

- [01_ConfigOverview.md](./01_ConfigOverview.md) - 系统概述
- [02_ConfigDirectory.md](./02_ConfigDirectory.md) - 目录结构
- [03_ConfigInheritance.md](./03_ConfigInheritance.md) - 继承规则
- [04_ConfigMergeRules.md](./04_ConfigMergeRules.md) - 合并规则
- [05_ConfigLoading.md](./05_ConfigLoading.md) - 加载流程
- [06_ConfigExamples.md](./06_ConfigExamples.md) - 示例大全
- [07_ErrorHandling.md](./07_ErrorHandling.md) - 错误处理
- [08_ImplementationAlgorithm.md](./08_ImplementationAlgorithm.md) - 算法实现

---

## 技术支持

如遇问题，请联系：
- 开发者: chenzhixu
- 代码位置: `server/routers/configTool.py`
- 文档位置: `docs/config/`
