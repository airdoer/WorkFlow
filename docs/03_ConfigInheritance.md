# 配置继承规则 (parent)

## 1. 继承机制概述

配置文件通过 `parent` 字段实现继承关系，子配置会继承父配置的所有字段，并可以选择性地覆盖部分字段。

### 1.1 基本语法

```json
{
  "parent": "conf_linux.json",
  "common": {
    "namespace": "c7_partner"
  }
}
```

- **parent 字段**: 指定父配置文件的路径
- **路径类型**: 支持相对路径和绝对路径

## 2. 路径解析规则

### 2.1 相对路径
相对路径相对于**当前配置文件所在的目录**

```json
// 文件: production/c7_partner.json
{
  "parent": "../conf_linux.json"  // 指向上级目录的 conf_linux.json
}
```

```json
// 文件: local/c7_dev_weekly.json
{
  "parent": "./c7_dev_weekly.generated.json"  // 指向同目录的文件
}
```

### 2.2 绝对路径
绝对路径相对于**配置根目录** (`//C7/Development/Mainline/Server/config/`)

```json
// 任意位置的配置文件
{
  "parent": "conf_linux.json"  // 相对于根目录
}
```

```json
{
  "parent": "production/c7_weekly.json"  // 明确指定子目录
}
```

### 2.3 路径解析优先级

1. **相对路径优先**: 如果路径以 `./` 或 `../` 开头，按相对路径处理
2. **绝对路径兜底**: 否则按配置根目录的绝对路径处理

```python
def resolve_parent_path(current_file: str, parent_path: str) -> str:
    if parent_path.startswith('./') or parent_path.startswith('../'):
        # 相对路径：相对于当前文件所在目录
        current_dir = os.path.dirname(current_file)
        return os.path.normpath(os.path.join(current_dir, parent_path))
    else:
        # 绝对路径：相对于配置根目录
        return os.path.join(CONFIG_ROOT, parent_path)
```

## 3. 继承链示例

### 3.1 单层继承

```
conf_base.json
    ↑
    | (parent)
conf_linux.json
```

**conf_base.json**:
```json
{
  "common": {
    "logTag": "c7",
    "entityDefPath": "../../../Client/Content/Script/Data/NetDefs/"
  }
}
```

**conf_linux.json**:
```json
{
  "parent": "./conf_base.json",
  "common": {
    "rsaPrivateKey": "config/rsa_prikey.pem",
    "serverZoneId": 8
  }
}
```

**合并结果**:
```json
{
  "common": {
    "logTag": "c7",
    "entityDefPath": "../../../Client/Content/Script/Data/NetDefs/",
    "rsaPrivateKey": "config/rsa_prikey.pem",
    "serverZoneId": 8
  }
}
```

### 3.2 多层继承

```
conf_base.json
    ↑
conf_linux.json
    ↑
c7_dev_weekly.generated.json
    ↑
c7_dev_weekly.json
```

**继承链加载顺序**:
1. 从最底层的 `c7_dev_weekly.json` 开始
2. 递归查找父配置：`c7_dev_weekly.generated.json`
3. 继续查找：`conf_linux.json`
4. 继续查找：`conf_base.json`（无 parent，停止）
5. **反向合并**：从根到子依次合并（`conf_base` → `conf_linux` → `generated` → `c7_dev_weekly`）

## 4. 循环继承检测

系统必须检测并防止循环继承，否则会导致无限递归。

### 4.1 循环继承示例

```json
// file_a.json
{
  "parent": "file_b.json"
}

// file_b.json
{
  "parent": "file_c.json"
}

// file_c.json
{
  "parent": "file_a.json"  // 循环！
}
```

### 4.2 检测算法

```python
def load_config_with_inheritance(file_path: str, visited: set = None) -> dict:
    if visited is None:
        visited = set()
    
    # 规范化路径
    abs_path = os.path.abspath(file_path)
    
    # 检测循环
    if abs_path in visited:
        raise CircularInheritanceError(f"Circular inheritance detected: {abs_path}")
    
    visited.add(abs_path)
    
    # 读取当前配置
    with open(abs_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 检查是否有父配置
    if 'parent' not in config:
        return config
    
    # 解析父配置路径
    parent_path = resolve_parent_path(abs_path, config['parent'])
    
    # 递归加载父配置
    parent_config = load_config_with_inheritance(parent_path, visited.copy())
    
    # 合并配置（父 <- 子）
    return deep_merge(parent_config, config)
```

### 4.3 错误提示

当检测到循环继承时，应提供清晰的错误信息：

```
Error: Circular inheritance detected in config files
Inheritance chain:
  c7_dev_weekly.json
  → c7_dev_weekly.generated.json
  → conf_linux.json
  → c7_dev_weekly.json  (circular reference)
```

## 5. 继承覆盖规则

### 5.1 对象字段覆盖

子配置的对象字段会**递归合并**到父配置的对象字段中。

**父配置**:
```json
{
  "common": {
    "namespace": "c7_base",
    "logLevel": "info",
    "manager_cluster": [{"peer": 1, "ip": "127.0.0.1", "port": 7001}]
  }
}
```

**子配置**:
```json
{
  "parent": "parent.json",
  "common": {
    "namespace": "c7_partner",
    "serverZoneId": 217
  }
}
```

**合并结果**:
```json
{
  "common": {
    "namespace": "c7_partner",      // 子覆盖父
    "logLevel": "info",             // 继承自父
    "serverZoneId": 217,            // 子新增
    "manager_cluster": [{"peer": 1, "ip": "127.0.0.1", "port": 7001}]  // 继承自父
  }
}
```

### 5.2 数组字段覆盖

数组字段采用**完全替换**策略（不合并）。

**父配置**:
```json
{
  "common": {
    "logic_server_list": [50001, 50002, 50003]
  }
}
```

**子配置**:
```json
{
  "parent": "parent.json",
  "common": {
    "logic_server_list": [50066]
  }
}
```

**合并结果**:
```json
{
  "common": {
    "logic_server_list": [50066]  // 完全替换，不保留父的值
  }
}
```

### 5.3 基本类型覆盖

字符串、数字、布尔值等基本类型采用**直接覆盖**。

**父配置**:
```json
{
  "logic": {
    "database": "c7_base",
    "lua_call_timeout": 3000
  }
}
```

**子配置**:
```json
{
  "parent": "parent.json",
  "logic": {
    "database": "c7_partner",
    "lua_call_timeout": 5000
  }
}
```

**合并结果**:
```json
{
  "logic": {
    "database": "c7_partner",      // 覆盖
    "lua_call_timeout": 5000       // 覆盖
  }
}
```

## 6. 特殊字段处理

### 6.1 parent 字段不继承

`parent` 字段仅用于指示继承关系，不会出现在最终合并结果中。

**输入**:
```json
{
  "parent": "conf_base.json",
  "common": {
    "namespace": "c7_test"
  }
}
```

**输出** (parent 字段被移除):
```json
{
  "common": {
    "namespace": "c7_test"
  }
}
```

### 6.2 null 值的处理

- **null 作为覆盖值**: 如果子配置显式设置某字段为 `null`，则覆盖父配置的值
- **删除字段**: 如果需要删除父配置的字段，可设置为 `null`

**父配置**:
```json
{
  "common": {
    "enablePay": true,
    "payNotifyUrl": "http://example.com/pay"
  }
}
```

**子配置**:
```json
{
  "parent": "parent.json",
  "common": {
    "payNotifyUrl": null  // 显式设置为 null
  }
}
```

**合并结果**:
```json
{
  "common": {
    "enablePay": true,
    "payNotifyUrl": null  // 保留 null
  }
}
```

## 7. 实际应用场景

### 7.1 环境差异化配置

```
conf_base.json (基础配置)
    ↑
conf_linux.json (Linux 环境配置)
    ↑
c7_weekly.json (weekly 环境，生产配置)
    ↑
c7_dev_weekly.json (开发环境，覆盖数据库/Redis等)
```

### 7.2 进程实例配置继承

虽然 `logic_1`, `logic_2` 等不使用 `parent` 字段，但它们通过配置加载逻辑继承 `logic` 和 `common` 的配置。

详细说明见 [04_ConfigMergeRules.md](./04_ConfigMergeRules.md) 和 [05_ConfigLoading.md](./05_ConfigLoading.md)。
