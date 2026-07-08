# 错误处理

本文档描述配置系统可能遇到的错误及其处理方式。

## 1. 错误分类

| 错误类型 | HTTP状态码 | 说明 |
|---------|-----------|------|
| 文件不存在 | 404 | 配置文件或父配置文件不存在 |
| JSON解析错误 | 400 | 配置文件不是有效的JSON格式 |
| 循环继承 | 400 | 检测到循环继承关系 |
| P4同步失败 | 500 | 从P4同步文件失败 |
| 非法路径 | 400 | 路径格式错误或包含非法字符 |
| 参数错误 | 400 | 请求参数缺失或格式错误 |

## 2. 文件不存在错误

### 2.1 主配置文件不存在

**场景**: 请求的环境配置文件不存在

**示例请求**:
```http
GET /getConfig?env=invalid_env&syncP4=true
```

**错误响应**:
```json
{
  "errMsg": "Config file not found: E:/Project/C7_project/Server/config/production/invalid_env.json",
  "p4Path": "//C7/Development/Mainline/Server/config/production/invalid_env.json",
  "localPath": "E:/Project/C7_project/Server/config/production/invalid_env.json",
  "suggestion": "Check if the environment name is correct or if the file exists in P4"
}
```

**HTTP状态码**: `404`

**处理建议**:
1. 检查环境名称是否正确
2. 确认文件在P4中存在
3. 检查P4工作区映射是否正确

---

### 2.2 父配置文件不存在

**场景**: 配置文件的parent字段指向的文件不存在

**配置文件** (c7_test.json):
```json
{
  "parent": "non_existent_parent.json",
  "common": {
    "namespace": "c7_test"
  }
}
```

**错误响应**:
```json
{
  "errMsg": "Parent config file not found",
  "currentFile": "E:/Project/C7_project/Server/config/production/c7_test.json",
  "parentPath": "non_existent_parent.json",
  "resolvedPath": "E:/Project/C7_project/Server/config/non_existent_parent.json",
  "suggestion": "Check the 'parent' field in the config file"
}
```

**HTTP状态码**: `404`

**处理建议**:
1. 检查parent路径是否正确
2. 确认父配置文件存在
3. 检查相对路径或绝对路径的使用是否正确

---

## 3. JSON解析错误

### 3.1 语法错误

**场景**: 配置文件包含非法JSON语法

**错误配置文件**:
```json
{
  "common": {
    "namespace": "c7_test",
    "logLevel": "info"  // 缺少闭合大括号
  }
```

**错误响应**:
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

**HTTP状态码**: `400`

---

### 3.2 非法字符

**场景**: JSON文件包含非法字符

**错误配置文件**:
```json
{
  "common": {
    "namespace": "c7_test"，  // 中文逗号
    "logLevel": "info"
  }
}
```

**错误响应**:
```json
{
  "errMsg": "Invalid JSON format in config file",
  "file": "E:/Project/C7_project/Server/config/production/c7_test.json",
  "error": "Invalid character in string",
  "line": 3,
  "column": 29,
  "suggestion": "Check for non-ASCII characters or invalid escape sequences"
}
```

**HTTP状态码**: `400`

---

### 3.3 编码问题

**场景**: 配置文件使用了错误的编码

**错误响应**:
```json
{
  "errMsg": "Failed to decode config file",
  "file": "E:/Project/C7_project/Server/config/production/c7_test.json",
  "error": "'utf-8' codec can't decode byte 0xff",
  "suggestion": "Ensure the config file is saved with UTF-8 encoding"
}
```

**HTTP状态码**: `400`

---

## 4. 循环继承错误

### 4.1 简单循环

**场景**: 两个文件互相继承

**file_a.json**:
```json
{
  "parent": "file_b.json",
  "common": {"keyA": "valueA"}
}
```

**file_b.json**:
```json
{
  "parent": "file_a.json",
  "common": {"keyB": "valueB"}
}
```

**错误响应**:
```json
{
  "errMsg": "Circular inheritance detected in config files",
  "inheritanceChain": "file_a.json -> file_b.json -> file_a.json",
  "files": [
    "E:/Project/C7_project/Server/config/file_a.json",
    "E:/Project/C7_project/Server/config/file_b.json"
  ],
  "suggestion": "Remove circular references from the 'parent' fields"
}
```

**HTTP状态码**: `400`

---

### 4.2 复杂循环

**场景**: 多个文件形成循环

**file_a.json** → **file_b.json** → **file_c.json** → **file_a.json**

**错误响应**:
```json
{
  "errMsg": "Circular inheritance detected in config files",
  "inheritanceChain": "file_a.json -> file_b.json -> file_c.json -> file_a.json",
  "files": [
    "E:/Project/C7_project/Server/config/file_a.json",
    "E:/Project/C7_project/Server/config/file_b.json",
    "E:/Project/C7_project/Server/config/file_c.json"
  ],
  "suggestion": "Check the inheritance chain and remove circular references"
}
```

**HTTP状态码**: `400`

---

### 4.3 自引用

**场景**: 文件的parent指向自己

**file.json**:
```json
{
  "parent": "file.json",
  "common": {"key": "value"}
}
```

**错误响应**:
```json
{
  "errMsg": "Self-referencing parent detected",
  "file": "E:/Project/C7_project/Server/config/file.json",
  "suggestion": "A config file cannot have itself as a parent"
}
```

**HTTP状态码**: `400`

---

## 5. P4同步错误

### 5.1 P4连接失败

**场景**: 无法连接到P4服务器

**错误响应**:
```json
{
  "errMsg": "Failed to sync config from P4",
  "p4Path": "//C7/Development/Mainline/Server/config/production/c7_partner.json",
  "error": "Perforce client error: Connection timeout",
  "suggestion": "Check P4 server connection or network status"
}
```

**HTTP状态码**: `500`

---

### 5.2 P4权限不足

**场景**: 没有读取P4文件的权限

**错误响应**:
```json
{
  "errMsg": "Failed to sync config from P4",
  "p4Path": "//C7/Development/Mainline/Server/config/production/c7_partner.json",
  "error": "Access denied: You don't have permission to read this file",
  "suggestion": "Contact P4 administrator to grant read permissions"
}
```

**HTTP状态码**: `403`

---

### 5.3 P4文件不存在

**场景**: P4中文件不存在

**错误响应**:
```json
{
  "errMsg": "Config file not found in P4",
  "p4Path": "//C7/Development/Mainline/Server/config/production/c7_test.json",
  "error": "No such file(s)",
  "suggestion": "Check if the file exists in the specified P4 path"
}
```

**HTTP状态码**: `404`

---

## 6. 路径错误

### 6.1 非法路径字符

**场景**: 路径包含非法字符

**错误配置**:
```json
{
  "parent": "../../../etc/passwd",
  "common": {}
}
```

**错误响应**:
```json
{
  "errMsg": "Invalid parent path",
  "parentPath": "../../../etc/passwd",
  "error": "Path escapes the config root directory",
  "suggestion": "Parent paths must be within the config directory"
}
```

**HTTP状态码**: `400`

---

### 6.2 绝对路径穿越

**场景**: 尝试访问配置目录外的文件

**错误配置**:
```json
{
  "parent": "/etc/passwd",
  "common": {}
}
```

**错误响应**:
```json
{
  "errMsg": "Invalid parent path",
  "parentPath": "/etc/passwd",
  "error": "Absolute system paths are not allowed",
  "suggestion": "Use relative paths within the config directory"
}
```

**HTTP状态码**: `400`

---

## 7. 参数错误

### 7.1 缺少必需参数

**场景**: 请求缺少必需的env参数

**请求**:
```http
GET /getConfig?syncP4=true
```

**错误响应**:
```json
{
  "errMsg": "Missing required parameter: env",
  "requiredParams": ["env"],
  "providedParams": {"syncP4": "true"},
  "example": "/getConfig?env=c7_partner&syncP4=false"
}
```

**HTTP状态码**: `400`

---

### 7.2 参数值非法

**场景**: 参数值不在允许范围内

**请求**:
```http
GET /getConfig?env=c7_partner&branchType=invalid_branch
```

**错误响应**:
```json
{
  "errMsg": "Invalid parameter value: branchType",
  "parameter": "branchType",
  "providedValue": "invalid_branch",
  "allowedValues": ["mainline", "weekly"],
  "suggestion": "Use one of the allowed values"
}
```

**HTTP状态码**: `400`

---

### 7.3 processId格式错误

**场景**: processId不是有效的整数

**请求**:
```http
GET /getConfig?env=c7_partner&processType=logic&processId=abc
```

**错误响应**:
```json
{
  "errMsg": "Invalid parameter type: processId",
  "parameter": "processId",
  "providedValue": "abc",
  "expectedType": "integer",
  "suggestion": "processId must be a positive integer"
}
```

**HTTP状态码**: `400`

---

## 8. 其他错误

### 8.1 磁盘空间不足

**场景**: 无法写入本地缓存文件

**错误响应**:
```json
{
  "errMsg": "Failed to write config cache",
  "error": "No space left on device",
  "localPath": "E:/Project/C7_project/Server/config/.cache/",
  "suggestion": "Free up disk space or check file system permissions"
}
```

**HTTP状态码**: `500`

---

### 8.2 配置文件过大

**场景**: 配置文件超过大小限制

**错误响应**:
```json
{
  "errMsg": "Config file too large",
  "file": "E:/Project/C7_project/Server/config/production/c7_test.json",
  "fileSize": 104857600,
  "maxSize": 10485760,
  "suggestion": "Config files should not exceed 10MB"
}
```

**HTTP状态码**: `413`

---

## 9. 错误处理最佳实践

### 9.1 错误日志记录

在处理错误时，应记录详细的日志信息：

```python
app.logger.error(
    f"Config load failed: env={env}, error={str(e)}",
    extra={
        'env': env,
        'branchType': branchType,
        'p4Path': p4_path,
        'localPath': local_path,
        'errorType': type(e).__name__,
        'stackTrace': traceback.format_exc()
    }
)
```

---

### 9.2 用户友好的错误提示

错误响应应包含：
- **errMsg**: 简明的错误描述
- **详细信息**: 相关的文件路径、参数值等
- **suggestion**: 解决建议
- **example**: 正确的使用示例（如果适用）

---

### 9.3 错误恢复

对于可恢复的错误，系统应尝试降级策略：

1. **缓存降级**: P4同步失败时，使用旧缓存（如果存在）
2. **默认值**: 部分字段缺失时，使用合理的默认值
3. **部分成功**: 多个配置文件加载时，返回成功加载的部分

**示例** (降级响应):
```json
{
  "warning": "P4 sync failed, using cached config",
  "cacheTimestamp": 1704067200,
  "cacheAge": 3600,
  "data": {
    ...
  }
}
```

**HTTP状态码**: `200` (但包含warning字段)

---

## 10. 错误处理代码示例

### 10.1 统一错误处理函数

```python
def handle_config_error(e: Exception, context: dict) -> tuple:
    """
    统一错误处理函数
    
    返回: (response_json, status_code)
    """
    if isinstance(e, FileNotFoundError):
        return jsonify({
            'errMsg': 'Config file not found',
            'file': str(e),
            'p4Path': context.get('p4Path'),
            'localPath': context.get('localPath'),
            'suggestion': 'Check if the file exists in P4'
        }), 404
    
    elif isinstance(e, json.JSONDecodeError):
        return jsonify({
            'errMsg': 'Invalid JSON format',
            'file': context.get('localPath'),
            'error': str(e),
            'line': e.lineno,
            'column': e.colno,
            'suggestion': 'Fix JSON syntax errors'
        }), 400
    
    elif isinstance(e, CircularInheritanceError):
        return jsonify({
            'errMsg': 'Circular inheritance detected',
            'inheritanceChain': e.chain,
            'files': e.files,
            'suggestion': 'Remove circular references'
        }), 400
    
    elif isinstance(e, P4SyncError):
        return jsonify({
            'errMsg': 'Failed to sync from P4',
            'p4Path': context.get('p4Path'),
            'error': str(e),
            'suggestion': 'Check P4 connection or permissions'
        }), 500
    
    else:
        # 未知错误
        app.logger.error(f"Unexpected error: {e}", exc_info=True)
        return jsonify({
            'errMsg': 'Internal server error',
            'error': str(e),
            'suggestion': 'Contact system administrator'
        }), 500
```

---

### 10.2 自定义异常类

```python
class ConfigError(Exception):
    """配置系统基础异常类"""
    pass

class CircularInheritanceError(ConfigError):
    """循环继承错误"""
    def __init__(self, chain: list):
        self.chain = ' -> '.join(chain)
        self.files = chain
        super().__init__(f"Circular inheritance: {self.chain}")

class P4SyncError(ConfigError):
    """P4同步错误"""
    pass

class ConfigParseError(ConfigError):
    """配置解析错误"""
    pass

class InvalidPathError(ConfigError):
    """非法路径错误"""
    pass
```

---

### 10.3 使用示例

```python
@app.route('/getConfig', methods=['GET'])
def getConfig():
    try:
        env = request.args.get('env')
        if not env:
            return jsonify({
                'errMsg': 'Missing required parameter: env',
                'example': '/getConfig?env=c7_partner'
            }), 400
        
        branchType = request.args.get('branchType', 'mainline')
        syncP4 = parse_bool(request.args.get('syncP4'), default=False)
        
        # 构建路径
        p4_path, local_path = build_config_path(env, branchType)
        
        # 同步文件
        if syncP4:
            sync_p4_file(p4_path, local_path)
        
        # 加载配置
        config = load_config_with_inheritance(local_path)
        
        # 返回结果
        return jsonify({
            'env': env,
            'branchType': branchType,
            'configP4Path': p4_path,
            'data': config
        })
    
    except Exception as e:
        context = {
            'env': env,
            'branchType': branchType,
            'p4Path': p4_path,
            'localPath': local_path
        }
        return handle_config_error(e, context)
```
