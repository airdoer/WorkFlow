# C7 配置系统文档

## 文档概述

本目录包含 C7 服务器配置系统的完整规范文档，包括配置继承、合并规则、加载流程、错误处理等。

## 文档结构

| 文档 | 说明 |
|------|------|
| [01_ConfigOverview.md](./01_ConfigOverview.md) | 系统概述：配置系统的整体介绍、层级结构、P4路径、关键特性 |
| [02_ConfigDirectory.md](./02_ConfigDirectory.md) | 目录结构：P4仓库结构、本地映射、目录功能、文件命名规范 |
| [03_ConfigInheritance.md](./03_ConfigInheritance.md) | parent继承规则：路径解析、继承链、循环检测、覆盖规则 |
| [04_ConfigMergeRules.md](./04_ConfigMergeRules.md) | 合并规则：对象递归合并、数组替换、基本类型覆盖、进程级配置 |
| [05_ConfigLoading.md](./05_ConfigLoading.md) | 加载流程：详细的加载步骤、配置优先级、缓存策略、性能优化 |
| [06_ConfigExamples.md](./06_ConfigExamples.md) | 大量示例：继承、合并、进程配置、真实场景的输入输出示例 |
| [07_ErrorHandling.md](./07_ErrorHandling.md) | 错误处理：错误分类、错误响应格式、错误处理最佳实践 |
| [08_ImplementationAlgorithm.md](./08_ImplementationAlgorithm.md) | 算法实现：伪代码、复杂度分析、测试用例、优化建议 |

## 快速开始

### 1. 理解配置系统

**新手推荐阅读顺序**:
1. [01_ConfigOverview.md](./01_ConfigOverview.md) - 了解系统全貌
2. [06_ConfigExamples.md](./06_ConfigExamples.md) - 通过示例学习
3. [03_ConfigInheritance.md](./03_ConfigInheritance.md) - 掌握继承规则
4. [04_ConfigMergeRules.md](./04_ConfigMergeRules.md) - 理解合并逻辑

**开发者推荐阅读顺序**:
1. [08_ImplementationAlgorithm.md](./08_ImplementationAlgorithm.md) - 算法实现
2. [05_ConfigLoading.md](./05_ConfigLoading.md) - 加载流程细节
3. [07_ErrorHandling.md](./07_ErrorHandling.md) - 错误处理
4. [02_ConfigDirectory.md](./02_ConfigDirectory.md) - 目录结构

### 2. API 使用

#### 2.1 获取完整配置

```http
GET /getConfig?env=c7_partner&syncP4=false
```

**响应**:
```json
{
  "env": "c7_partner",
  "branchType": "mainline",
  "configP4Path": "//C7/Development/Mainline/Server/config/production/c7_partner.json",
  "configChangelist": 12345,
  "data": {
    "common": {...},
    "logic": {...},
    "logic_1": {...}
  }
}
```

#### 2.2 获取进程配置

```http
GET /getConfig?env=c7_partner&processType=logic&processId=1&syncP4=false
```

**响应**:
```json
{
  "env": "c7_partner",
  "processType": "logic",
  "processId": 1,
  "data": {
    "namespace": "c7_partner",
    "logLevel": "info",
    "lua_call_timeout": 5000,
    "ip": "inner_ip1",
    ...
  }
}
```

#### 2.3 清除缓存

```http
POST /clearConfigCache?env=c7_partner
```

### 3. 配置文件示例

#### 3.1 简单配置

```json
{
  "parent": "conf_linux.json",
  "common": {
    "namespace": "c7_test",
    "logLevel": "info"
  },
  "logic": {
    "database": "c7_test"
  },
  "logic_1": {
    "ip": "127.0.0.1",
    "port": 7601
  }
}
```

#### 3.2 配置继承链

```
conf_base.json
    ↓ (parent)
conf_linux.json
    ↓ (parent)
c7_partner.json
```

## 核心概念

### 1. namespace 唯一标识

每个配置文件的 `common` 块中必须包含唯一的 `namespace` 字段：

```json
{
  "common": {
    "namespace": "c7_partner",  // 环境唯一标识符
    "logLevel": "info"
  }
}
```

**namespace 作用**：
- ✅ 环境唯一标识，区分不同环境
- ✅ 新建配置的唯一 Key
- ✅ 服务器运行时识别
- ✅ 日志和监控标记
- ⚠️ 必须全局唯一

### 2. 配置层级

```
common (通用配置)
   ↓
logic (进程类型配置)
   ↓
logic_1 (具体进程配置)
```

### 3. 合并策略

| 数据类型 | 合并策略 |
|---------|---------|
| 对象 | 递归合并，子覆盖父 |
| 数组 | 完全替换 |
| 基本类型 | 直接覆盖 |

### 4. 配置优先级

**继承链优先级** (从低到高):
```
基础配置 → 平台配置 → 环境配置
```

**进程级优先级** (从低到高):
```
common → processType → processType_id
```

### 5. 分支类型

支持三种 P4 分支：
- `mainline` - 主干开发分支（默认）
- `weekly` - 周版本分支
- `preonline` - 预发布分支

## 实现代码

配置系统的实现代码位于:
- **Router**: `server/routers/configTool.py`
- **核心函数**:
  - `deep_merge()` - 深度合并算法
  - `load_config_with_inheritance()` - 递归加载配置
  - `extract_process_config()` - 提取进程配置
  - `resolve_parent_path()` - 解析parent路径

## 常见问题

### Q1: 为什么数组不合并而是完全替换？

**A**: 数组完全替换的设计理由：
1. **语义清晰**: 数组通常表示一个完整的列表，部分合并会导致语义不明确
2. **避免重复**: 合并数组元素可能导致重复项
3. **简化逻辑**: 数组元素可能是对象，对象的合并条件难以定义

### Q2: 如何避免循环继承？

**A**: 系统会自动检测循环继承，当检测到时会抛出 `CircularInheritanceError`。确保配置文件的 parent 字段不形成循环引用。

### Q3: 缓存何时失效？

**A**: 缓存在以下情况失效：
1. P4文件的 changelist 发生变化
2. 请求参数 `syncP4=true` 强制刷新
3. 手动调用 `/clearConfigCache` 清除缓存

### Q4: 如何处理多环境配置？

**A**: 使用继承链：
```
conf_base.json (基础配置)
  ↓
conf_linux.json (平台配置)
  ↓
c7_weekly.json (生产配置)
  ↓
c7_dev_weekly.json (开发环境，覆盖数据库等敏感配置)
```

## 最佳实践

### 1. 配置文件组织

- **基础配置** (conf_base.json): 定义所有环境通用的配置
- **平台配置** (conf_linux.json): 定义特定平台的配置
- **环境配置** (c7_*.json): 定义特定环境的配置

### 2. 字段命名

- 使用驼峰命名: `logLevel`, `serverZoneId`
- 布尔字段使用 `enable` 前缀: `enablePay`, `compressEnabled`
- 复数表示数组: `logic_server_list`, `manager_cluster`

### 3. 敏感信息

- 密码、密钥等敏感信息应使用占位符，实际值由部署系统注入
- 示例: `"password": "redis-passwd"` (占位符)

### 4. 版本管理

- 配置文件应纳入版本控制 (P4)
- 重要变更应添加 changelist 描述
- 生产配置变更需要 Code Review

## 性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 配置加载时间 | < 100ms | 包含P4同步 |
| 缓存命中率 | > 95% | 正常运行时 |
| 内存占用 | ~10MB | 缓存100个配置 |
| 支持配置大小 | < 10MB | 单个配置文件 |

## 相关资源

- **P4路径**: `//C7/Development/Mainline/Server/config/`
- **本地路径**: `E:\Project\C7_project\Server\config\`
- **API文档**: 见各文档的 API 示例章节
- **代码实现**: `server/routers/configTool.py`

## 更新日志

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-07-04 | v1.0 | 初始版本，完整的配置系统规范文档 |

## 贡献者

- 文档编写: AI Assistant
- 需求提供: chenzhixu

## 许可证

内部文档，仅供 C7 项目团队使用。
