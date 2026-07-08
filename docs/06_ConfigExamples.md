# 配置示例

本文档提供大量输入/输出示例，帮助理解配置系统的工作方式。

## 1. 基础继承示例

### 示例1.1: 单层继承

**输入文件**:

`conf_base.json`:
```json
{
  "common": {
    "logTag": "c7",
    "compressEnabled": true,
    "serverZoneId": 1
  }
}
```

`c7_test.json`:
```json
{
  "parent": "conf_base.json",
  "common": {
    "namespace": "c7_test",
    "serverZoneId": 100
  }
}
```

**输出** (加载 `c7_test.json`):
```json
{
  "common": {
    "logTag": "c7",
    "compressEnabled": true,
    "namespace": "c7_test",
    "serverZoneId": 100
  }
}
```

**说明**: `serverZoneId` 被子配置覆盖为 100

---

### 示例1.2: 多层继承

**输入文件**:

`conf_base.json`:
```json
{
  "common": {
    "logLevel": "debug"
  }
}
```

`conf_linux.json`:
```json
{
  "parent": "conf_base.json",
  "common": {
    "logLevel": "info",
    "luaLoaderFile": "/Engine/Loader.lua"
  }
}
```

`c7_partner.json`:
```json
{
  "parent": "conf_linux.json",
  "common": {
    "namespace": "c7_partner",
    "serverZoneId": 217
  }
}
```

**输出** (加载 `c7_partner.json`):
```json
{
  "common": {
    "logLevel": "info",
    "luaLoaderFile": "/Engine/Loader.lua",
    "namespace": "c7_partner",
    "serverZoneId": 217
  }
}
```

**继承链**: `conf_base.json` → `conf_linux.json` → `c7_partner.json`

---

## 2. 对象合并示例

### 示例2.1: 嵌套对象合并

**父配置**:
```json
{
  "common": {
    "kcp": {
      "mtu": 996,
      "magic": 59038,
      "nodelay": 1,
      "interval": 10
    }
  }
}
```

**子配置**:
```json
{
  "parent": "parent.json",
  "common": {
    "kcp": {
      "mtu": 1200,
      "timeout": 30000
    }
  }
}
```

**输出**:
```json
{
  "common": {
    "kcp": {
      "mtu": 1200,       // 覆盖
      "magic": 59038,    // 继承
      "nodelay": 1,      // 继承
      "interval": 10,    // 继承
      "timeout": 30000   // 新增
    }
  }
}
```

---

### 示例2.2: 深层嵌套对象

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
        "host": "127.0.0.1",
        "port": 8501
      }
    }
  }
}
```

**输出**:
```json
{
  "logic": {
    "http": {
      "AdminService": {
        "host": "0.0.0.0",    // 继承
        "port": 8800,         // 覆盖
        "timeout": 30         // 继承
      },
      "TelnetService": {
        "host": "127.0.0.1",  // 新增
        "port": 8501          // 新增
      }
    }
  }
}
```

---

## 3. 数组替换示例

### 示例3.1: 基本类型数组

**父配置**:
```json
{
  "common": {
    "logic_server_list": [50001, 50002, 50003, 50004]
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

**输出**:
```json
{
  "common": {
    "logic_server_list": [50066]  // 完全替换
  }
}
```

**说明**: 数组不合并，子配置的数组完全替换父配置的数组

---

### 示例3.2: 对象数组

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

**输出**:
```json
{
  "common": {
    "manager_cluster": [
      {"peer": 1, "ip": "127.0.0.1", "port": 7001}
    ]
  }
}
```

**说明**: 即使数组元素是对象，也采用完全替换策略

---

## 4. 进程级配置示例

### 示例4.1: 提取 logic_1 配置

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
  },
  "logic_2": {
    "ip": "inner_ip1",
    "console": {
      "ip": "127.0.0.1",
      "port": 7602
    }
  }
}
```

**请求参数**: `processType=logic`, `processId=1`

**输出**:
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

**合并顺序**: `common` → `logic` → `logic_1`

---

### 示例4.2: 进程级字段覆盖

**配置文件**:
```json
{
  "common": {
    "logLevel": "warn"
  },
  "logic": {
    "logLevel": "info"
  },
  "logic_1": {
    "logLevel": "debug"
  }
}
```

**请求参数**: `processType=logic`, `processId=1`

**输出**:
```json
{
  "logLevel": "debug"
}
```

**说明**: `logic_1` 的配置优先级最高，覆盖了 `logic` 和 `common` 的值

---

### 示例4.3: 不同进程实例

**配置文件**:
```json
{
  "common": {
    "namespace": "c7_test"
  },
  "logic": {
    "database": "c7_test"
  },
  "logic_1": {
    "ip": "127.0.0.1",
    "port": 7601
  },
  "logic_2": {
    "ip": "127.0.0.1",
    "port": 7602
  }
}
```

**请求1**: `processType=logic`, `processId=1`
```json
{
  "namespace": "c7_test",
  "database": "c7_test",
  "ip": "127.0.0.1",
  "port": 7601
}
```

**请求2**: `processType=logic`, `processId=2`
```json
{
  "namespace": "c7_test",
  "database": "c7_test",
  "ip": "127.0.0.1",
  "port": 7602
}
```

---

## 5. 复杂继承与合并示例

### 示例5.1: 完整示例

**conf_base.json**:
```json
{
  "common": {
    "logTag": "c7",
    "compressEnabled": true,
    "kcp": {
      "mtu": 996,
      "magic": 59038
    }
  },
  "logic": {
    "entityPath": ["entities", "microservices"]
  }
}
```

**conf_linux.json**:
```json
{
  "parent": "conf_base.json",
  "common": {
    "serverZoneId": 8,
    "kcp": {
      "nodelay": 1
    }
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
    "serverZoneId": 217,
    "logic_server_list": [50066]
  },
  "logic": {
    "database": "c7_partner",
    "lua_call_timeout": 5000
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

**请求**: `env=c7_partner`, `processType=logic`, `processId=1`

**处理步骤**:

1. **加载 conf_base.json**
2. **合并 conf_linux.json**
3. **合并 c7_partner.json**
4. **提取 logic_1 配置**

**最终输出**:
```json
{
  "logTag": "c7",
  "compressEnabled": true,
  "serverZoneId": 217,
  "namespace": "c7_partner",
  "logic_server_list": [50066],
  "kcp": {
    "mtu": 996,
    "magic": 59038,
    "nodelay": 1
  },
  "entityPath": ["entities", "microservices"],
  "profileOutPath": "../../profileOut/",
  "database": "c7_partner",
  "lua_call_timeout": 5000,
  "ip": "inner_ip1",
  "console": {
    "ip": "127.0.0.1",
    "port": 7601
  }
}
```

---

## 6. 真实生产配置示例

### 示例6.1: c7_partner 完整配置

基于实际文件的简化示例。

**请求**: `env=c7_partner`, `processType=logic`, `processId=1`

**输入** (c7_partner.json):
```json
{
  "parent": "conf_linux.json",
  "common": {
    "namespace": "c7_partner",
    "logLevel": "info",
    "logic_server_list": [50066],
    "startup": {
      "desired": {
        "logic": 2,
        "router": 1,
        "dbmgr": 1
      }
    },
    "manager_cluster": [
      {
        "peer": 1,
        "ip": "inner_ip1",
        "port": 7001
      }
    ],
    "serverZoneId": 217,
    "enablePay": true,
    "payNotifyUrl": "http://10.73.1.206:7800/c7_partner/pay/gm_pay_order_received"
  },
  "logic": {
    "lua_call_timeout": 5000,
    "lua_loop_timeout": 5000,
    "database": "c7_partner",
    "logic_server_database": {
      "50066": "c7_partner_logic"
    },
    "redis_cluster": [
      {
        "password": "redis-passwd",
        "nodes": [
          {
            "host": "redis-host",
            "port": 6379
          }
        ]
      }
    ]
  },
  "logic_1": {
    "ip": "inner_ip1",
    "console": {
      "ip": "127.0.0.1",
      "port": 7601
    },
    "metrics": {
      "host": "0.0.0.0",
      "port": 9104
    },
    "tag": [
      "LuaService",
      "BanClient"
    ],
    "prefer_dbmgr": {
      "ip": "inner_ip1",
      "port": 7201
    },
    "http": {
      "AdminService": {
        "host": "0.0.0.0",
        "port": 7800
      }
    }
  }
}
```

**输出** (简化，省略继承自 conf_linux 和 conf_base 的字段):
```json
{
  "namespace": "c7_partner",
  "logLevel": "info",
  "logic_server_list": [50066],
  "serverZoneId": 217,
  "enablePay": true,
  "payNotifyUrl": "http://10.73.1.206:7800/c7_partner/pay/gm_pay_order_received",
  "lua_call_timeout": 5000,
  "lua_loop_timeout": 5000,
  "database": "c7_partner",
  "logic_server_database": {
    "50066": "c7_partner_logic"
  },
  "redis_cluster": [
    {
      "password": "redis-passwd",
      "nodes": [{"host": "redis-host", "port": 6379}]
    }
  ],
  "ip": "inner_ip1",
  "console": {
    "ip": "127.0.0.1",
    "port": 7601
  },
  "metrics": {
    "host": "0.0.0.0",
    "port": 9104
  },
  "tag": ["LuaService", "BanClient"],
  "prefer_dbmgr": {
    "ip": "inner_ip1",
    "port": 7201
  },
  "http": {
    "AdminService": {
      "host": "0.0.0.0",
      "port": 7800
    }
  }
}
```

---

## 7. 特殊场景示例

### 示例7.1: null 值覆盖

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

**输出**:
```json
{
  "common": {
    "enablePay": true,
    "payNotifyUrl": null
  }
}
```

---

### 示例7.2: 类型不匹配覆盖

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

**输出**:
```json
{
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

**说明**: 数组覆盖对象

---

### 示例7.3: 空对象 vs 空数组

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

**输出**:
```json
{
  "common": {
    "settings": {"key": "value"},  // 空对象不覆盖
    "list": []                     // 空数组完全替换
  }
}
```

---

## 8. API响应示例

### 示例8.1: 获取完整配置

**请求**:
```http
GET /getConfig?env=c7_partner&branchType=mainline&syncP4=false
```

**响应**:
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
      ...
    },
    "logic": {
      "lua_call_timeout": 5000,
      ...
    },
    "logic_1": {
      "ip": "inner_ip1",
      ...
    },
    ...
  }
}
```

---

### 示例8.2: 获取进程配置

**请求**:
```http
GET /getConfig?env=c7_partner&processType=logic&processId=1&syncP4=false
```

**响应**:
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
    "lua_call_timeout": 5000,
    "database": "c7_partner",
    "ip": "inner_ip1",
    "console": {
      "ip": "127.0.0.1",
      "port": 7601
    },
    ...
  }
}
```

---

### 示例8.3: 错误响应

**请求**:
```http
GET /getConfig?env=invalid_env&syncP4=true
```

**响应**:
```json
{
  "errMsg": "Config file not found: E:/Project/C7_project/Server/config/production/invalid_env.json",
  "p4Path": "//C7/Development/Mainline/Server/config/production/invalid_env.json",
  "localPath": "E:/Project/C7_project/Server/config/production/invalid_env.json"
}
```

**HTTP状态码**: `404`
