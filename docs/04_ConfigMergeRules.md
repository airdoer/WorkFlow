# 配置合并规则

## 1. 合并策略总览

C7 配置系统采用**深度合并**策略，根据数据类型采用不同的合并规则：

| 数据类型 | 合并策略 | 说明 |
|---------|---------|------|
| **对象 (Object)** | 递归合并 | 子对象的字段覆盖父对象的同名字段，保留父对象的其他字段 |
| **数组 (Array)** | 完全替换 | 子数组完全替换父数组，不进行元素级合并 |
| **基本类型** | 直接覆盖 | 字符串、数字、布尔值、null 直接覆盖父值 |

## 2. 对象合并 (深度递归)

### 2.1 基本规则

对象采用**递归深度合并**：
- 子对象的字段覆盖父对象的同名字段
- 保留父对象中未被覆盖的字段
- 嵌套对象继续递归合并

### 2.2 示例

**父配置**:
```json
{
  "common": {
    "namespace": "c7_base",
    "logLevel": "info",
    "kcp": {
      "mtu": 996,
      "magic": 59038,
      "nodelay": 1
    }
  }
}
```

**子配置**:
```json
{
  "parent": "parent.json",
  "common": {
    "namespace": "c7_partner",
    "kcp": {
      "mtu": 1200
    },
    "serverZoneId": 217
  }
}
```

**合并结果**:
```json
{
  "common": {
    "namespace": "c7_partner",  // 覆盖
    "logLevel": "info",         // 继承自父
    "serverZoneId": 217,        // 新增
    "kcp": {
      "mtu": 1200,              // 覆盖
      "magic": 59038,           // 继承自父（递归合并）
      "nodelay": 1              // 继承自父（递归合并）
    }
  }
}
```

### 2.3 多层嵌套对象

对象可以嵌套任意深度，合并规则保持一致。

**父配置**:
```json
{
  "logic": {
    "http": {
      "AdminService": {
        "host": "0.0.0.0",
        "port": 7800,
        "timeout": 30
      }
    }
  }
}
```

**子配置**:
```json
{
  "parent": "parent.json",
  "logic": {
    "http": {
      "AdminService": {
        "port": 8800
      },
      "TelnetService": {
        "host": "0.0.0.0",
        "port": 8501
      }
    }
  }
}
```

**合并结果**:
```json
{
  "logic": {
    "http": {
      "AdminService": {
        "host": "0.0.0.0",      // 继承
        "port": 8800,           // 覆盖
        "timeout": 30           // 继承
      },
      "TelnetService": {        // 新增
        "host": "0.0.0.0",
        "port": 8501
      }
    }
  }
}
```

## 3. 数组合并 (完全替换)

### 3.1 基本规则

数组采用**完全替换**策略：
- 子配置的数组会完全替换父配置的数组
- 不进行元素级别的合并或去重
- 无论数组元素是对象还是基本类型，都采用完全替换

### 3.2 示例：基本类型数组

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
    "logic_server_list": [50066]  // 完全替换
  }
}
```

### 3.3 示例：对象数组

**父配置**:
```json
{
  "common": {
    "manager_cluster": [
      {"peer": 1, "ip": "inner_ip1", "port": 7001},
      {"peer": 2, "ip": "inner_ip2", "port": 7001},
      {"peer": 3, "ip": "inner_ip3", "port": 7001}
    ]
  }
}
```

**子配置**:
```json
{
  "parent": "parent.json",
  "common": {
    "manager_cluster": [
      {"peer": 1, "ip": "127.0.0.1", "port": 7001}
    ]
  }
}
```

**合并结果**:
```json
{
  "common": {
    "manager_cluster": [
      {"peer": 1, "ip": "127.0.0.1", "port": 7001}  // 完全替换
    ]
  }
}
```

### 3.4 为什么数组不合并？

**设计理由**:
1. **语义清晰**: 数组通常表示一个完整的列表，部分合并会导致语义不明确
2. **避免重复**: 如果合并数组元素，可能导致重复项
3. **简化逻辑**: 数组元素可能是对象，对象的合并条件难以定义（按什么字段匹配？）
4. **实际需求**: 在配置继承场景中，子配置通常需要完全自定义列表

**替代方案**: 如果需要追加元素，应在子配置中显式列出所有元素（包括父配置的元素）。

## 4. 基本类型覆盖

### 4.1 支持的基本类型

- `string` (字符串)
- `number` (数字)
- `boolean` (布尔值)
- `null` (空值)

### 4.2 覆盖规则

子配置的基本类型值会直接覆盖父配置的值。

**父配置**:
```json
{
  "logic": {
    "database": "c7_base",
    "lua_call_timeout": 3000,
    "enableFeatureX": true
  }
}
```

**子配置**:
```json
{
  "parent": "parent.json",
  "logic": {
    "database": "c7_partner",
    "lua_call_timeout": 5000,
    "enableFeatureX": false
  }
}
```

**合并结果**:
```json
{
  "logic": {
    "database": "c7_partner",      // 覆盖
    "lua_call_timeout": 5000,      // 覆盖
    "enableFeatureX": false        // 覆盖
  }
}
```

## 5. null 值处理

### 5.1 null 作为覆盖值

显式设置为 `null` 会覆盖父配置的值。

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
    "payNotifyUrl": null
  }
}
```

**合并结果**:
```json
{
  "common": {
    "enablePay": true,
    "payNotifyUrl": null  // 显式覆盖为 null
  }
}
```

### 5.2 删除字段

**注意**: 当前合并算法不支持删除父配置的字段，只能覆盖为 `null`。

如果需要完全删除字段，可以在应用层过滤 `null` 值。

## 6. 进程级配置合并

C7 配置系统有三层配置：`common` → 进程类型 (`logic`) → 进程实例 (`logic_1`)

### 6.1 合并流程

```
1. 加载并合并 parent 继承链
2. 提取 common 配置作为基础
3. 提取进程类型配置 (如 logic) 并合并到基础上
4. 提取具体进程实例配置 (如 logic_1) 并合并到上一步结果上
5. 返回最终配置
```

### 6.2 示例

**配置文件**:
```json
{
  "common": {
    "namespace": "c7_partner",
    "logLevel": "info"
  },
  "logic": {
    "lua_call_timeout": 5000,
    "database": "c7_partner"
  },
  "logic_1": {
    "ip": "inner_ip1",
    "console": {
      "ip": "127.0.0.1",
      "port": 7601
    }
  }
}
```

**请求参数**: `processType=logic`, `processId=1`

**合并步骤**:

1. **基础配置** (common):
```json
{
  "namespace": "c7_partner",
  "logLevel": "info"
}
```

2. **合并进程类型配置** (common + logic):
```json
{
  "namespace": "c7_partner",
  "logLevel": "info",
  "lua_call_timeout": 5000,
  "database": "c7_partner"
}
```

3. **合并具体进程配置** (上一步 + logic_1):
```json
{
  "namespace": "c7_partner",
  "logLevel": "info",
  "lua_call_timeout": 5000,
  "database": "c7_partner",
  "ip": "inner_ip1",
  "console": {
    "ip": "127.0.0.1",
    "port": 7601
  }
}
```

## 7. 合并算法伪代码

```python
def deep_merge(parent: dict, child: dict) -> dict:
    """
    深度合并两个字典
    
    规则:
    - 对象: 递归合并
    - 数组: 完全替换
    - 基本类型: 直接覆盖
    """
    result = parent.copy()
    
    for key, child_value in child.items():
        if key == 'parent':
            # 跳过 parent 字段
            continue
        
        if key not in result:
            # 新字段，直接添加
            result[key] = child_value
        else:
            parent_value = result[key]
            
            # 判断类型并合并
            if isinstance(child_value, dict) and isinstance(parent_value, dict):
                # 对象: 递归合并
                result[key] = deep_merge(parent_value, child_value)
            else:
                # 数组、基本类型、null: 直接覆盖
                result[key] = child_value
    
    return result


def merge_process_config(config: dict, process_type: str, process_id: int) -> dict:
    """
    合并进程级配置
    
    顺序: common -> logic -> logic_1
    """
    result = {}
    
    # 1. 合并 common
    if 'common' in config:
        result = deep_merge(result, config['common'])
    
    # 2. 合并进程类型配置
    if process_type in config:
        result = deep_merge(result, config[process_type])
    
    # 3. 合并具体进程实例配置
    process_key = f"{process_type}_{process_id}"
    if process_key in config:
        result = deep_merge(result, config[process_key])
    
    return result
```

## 8. 边界情况处理

### 8.1 类型不匹配

如果父子配置的同名字段类型不同，子配置直接覆盖。

**父配置**:
```json
{
  "common": {
    "redis_cluster": {
      "host": "127.0.0.1",
      "port": 6379
    }
  }
}
```

**子配置**:
```json
{
  "parent": "parent.json",
  "common": {
    "redis_cluster": [
      {
        "password": "redis-passwd",
        "nodes": [{"host": "redis-host", "port": 6379}]
      }
    ]
  }
}
```

**合并结果**:
```json
{
  "common": {
    "redis_cluster": [  // 数组覆盖对象
      {
        "password": "redis-passwd",
        "nodes": [{"host": "redis-host", "port": 6379}]
      }
    ]
  }
}
```

### 8.2 空对象和空数组

- **空对象 `{}`**: 会保留父配置的字段（因为没有覆盖）
- **空数组 `[]`**: 会替换父配置的数组为空数组

**父配置**:
```json
{
  "common": {
    "settings": {"key": "value"},
    "list": [1, 2, 3]
  }
}
```

**子配置**:
```json
{
  "parent": "parent.json",
  "common": {
    "settings": {},
    "list": []
  }
}
```

**合并结果**:
```json
{
  "common": {
    "settings": {"key": "value"},  // 保留父配置
    "list": []                     // 替换为空数组
  }
}
```

### 8.3 undefined vs null

- **undefined** (字段不存在): 保留父配置的值
- **null** (显式设置为 null): 覆盖为 null

```json
// 父配置
{"field": "value"}

// 子配置1: 字段不存在
{}
// 结果: {"field": "value"}

// 子配置2: 显式 null
{"field": null}
// 结果: {"field": null}
```

## 9. 完整合并示例

### 9.1 输入

**conf_base.json**:
```json
{
  "common": {
    "logTag": "c7",
    "compressEnabled": true
  }
}
```

**conf_linux.json**:
```json
{
  "parent": "conf_base.json",
  "common": {
    "serverZoneId": 8,
    "luaLoaderFile": "/Engine/Loader.lua"
  },
  "logic": {
    "profileOutPath": "../../profileOut/"
  }
}
```

**c7_partner.json**:
```json
{
  "parent": "conf_linux.json",
  "common": {
    "namespace": "c7_partner",
    "serverZoneId": 217
  },
  "logic": {
    "database": "c7_partner"
  },
  "logic_1": {
    "ip": "inner_ip1",
    "port": 7601
  }
}
```

### 9.2 合并步骤

**步骤1**: 加载 `conf_base.json`
```json
{
  "common": {
    "logTag": "c7",
    "compressEnabled": true
  }
}
```

**步骤2**: 合并 `conf_linux.json`
```json
{
  "common": {
    "logTag": "c7",
    "compressEnabled": true,
    "serverZoneId": 8,
    "luaLoaderFile": "/Engine/Loader.lua"
  },
  "logic": {
    "profileOutPath": "../../profileOut/"
  }
}
```

**步骤3**: 合并 `c7_partner.json`
```json
{
  "common": {
    "logTag": "c7",
    "compressEnabled": true,
    "namespace": "c7_partner",
    "serverZoneId": 217,
    "luaLoaderFile": "/Engine/Loader.lua"
  },
  "logic": {
    "profileOutPath": "../../profileOut/",
    "database": "c7_partner"
  },
  "logic_1": {
    "ip": "inner_ip1",
    "port": 7601
  }
}
```

**步骤4**: 提取 `logic_1` 配置 (processType=logic, processId=1)
```json
{
  "logTag": "c7",
  "compressEnabled": true,
  "namespace": "c7_partner",
  "serverZoneId": 217,
  "luaLoaderFile": "/Engine/Loader.lua",
  "profileOutPath": "../../profileOut/",
  "database": "c7_partner",
  "ip": "inner_ip1",
  "port": 7601
}
```
