# C7 配置系统概述

## 1. 系统简介

C7 配置系统是一个基于 JSON 的分层配置管理系统，支持：
- **继承机制**：通过 `parent` 字段实现配置继承
- **分层覆盖**：子配置可以覆盖父配置的字段
- **进程级配置**：支持 `common`、进程类型（如 `logic`）、具体进程实例（如 `logic_1`）三级配置

## 2. 配置层级

配置系统采用三层结构：

```
common (通用配置)
   ↓
logic/dbmgr/router/cluster_manager (进程类型配置)
   ↓
logic_1/dbmgr_1/router_1/cluster_manager_1 (具体进程配置)
```

### 配置优先级（从低到高）
1. **common**: 所有进程共享的基础配置
2. **进程类型配置** (如 `logic`): 特定类型进程的通用配置
3. **具体进程配置** (如 `logic_1`): 特定进程实例的配置

**覆盖规则**：优先级高的配置会覆盖优先级低的配置

## 3. P4 路径结构

```
//C7/Development/Mainline/Server/config/      # 主干分支
├── production/          # 生产环境配置
│   ├── c7_partner.json
│   ├── c7_weekly.json
│   └── ...
├── local/              # 本地测试环境配置
│   ├── c7_dev_weekly.json
│   ├── c7_qa1.json
│   └── ...
├── conf_base.json      # 基础配置
├── conf_linux.json     # Linux 环境配置
└── ...                 # 其他公共配置文件

//C7/Development/Weekly/Server/config/        # 周版本分支
└── (同上目录结构)

//C7/Release/Preonline/Server/config/         # 预发布分支
└── (同上目录结构)
```

## 4. 配置文件命名规范

- **环境配置文件**: `c7_<env_name>.json` (如 `c7_partner.json`, `c7_weekly.json`)
- **生成文件**: `*.generated.json` (由工具生成，包含完整合并后的配置)
- **基础配置**: `conf_*.json` (如 `conf_base.json`, `conf_linux.json`)

### namespace 字段说明
每个环境配置文件的 `common` 块中必须包含 `namespace` 字段：

```json
{
  "common": {
    "namespace": "c7_partner",  // 环境唯一标识符
    "logLevel": "info"
  }
}
```

**namespace 的作用**：
- ✅ **环境唯一标识**：区分不同的运行环境
- ✅ **新建配置的 Key**：创建新环境配置时使用
- ✅ **运行时识别**：服务器进程通过 namespace 识别当前环境
- ✅ **日志标记**：日志中使用 namespace 标识来源

**重要提示**：
- ⚠️ namespace 必须全局唯一
- ⚠️ 通常与配置文件名保持一致（去掉 `.json`）
- ⚠️ 一旦创建不建议修改

## 5. 关键特性

### 5.1 parent 继承
配置文件可以通过 `parent` 字段继承另一个配置文件：

```json
{
  "parent": "conf_linux.json",
  "common": {
    "namespace": "c7_partner"
  }
}
```

### 5.2 深度合并
- **对象**：递归合并，子覆盖父
- **数组**：完全替换（不合并）
- **基本类型**：直接覆盖

### 5.3 路径解析
- **相对路径**: `./conf_base.json` (相对于当前文件所在目录)
- **绝对路径**: `conf_linux.json` (相对于配置根目录)

## 6. 使用场景

### 6.1 获取完整配置
获取指定环境、指定进程的最终合并配置：
```
GET /getConfig?env=c7_weekly&processType=logic&processId=1
```

### 6.2 查看原始文件
获取配置文件的原始内容（未合并）：
```
GET /getConfigFile?path=production/c7_weekly.json
```

### 6.3 比对配置差异
比较两个环境的配置差异：
```
GET /diffConfig?env1=c7_weekly&env2=c7_partner&processType=logic
```

## 7. 配置加载流程

```
1. 读取目标配置文件
2. 检查是否有 parent 字段
3. 递归加载父配置（循环检测）
4. 从父到子依次合并配置
5. 根据进程类型和实例 ID 提取最终配置
6. 返回合并结果
```

详细流程见 [05_ConfigLoading.md](./05_ConfigLoading.md)

## 8. 错误处理

系统会处理以下错误情况：
- 文件不存在
- JSON 解析失败
- 循环继承
- 非法路径
- P4 同步失败

详细说明见 [07_ErrorHandling.md](./07_ErrorHandling.md)
