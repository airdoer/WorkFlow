# 实现算法

本文档提供配置系统的伪代码和算法流程，便于实现和理解。

## 1. 核心算法概览

```
算法流程:
1. 参数解析与校验
2. 路径构建 (P4路径 → 本地路径)
3. 缓存检查 (可选)
4. P4文件同步 (可选)
5. 递归加载配置 (含parent继承)
6. 深度合并配置
7. 提取进程级配置 (可选)
8. 缓存结果
9. 返回响应
```

## 2. 深度合并算法

### 2.1 伪代码

```python
def deep_merge(base: dict, override: dict) -> dict:
    """
    深度合并两个字典
    
    规则:
    - 对象: 递归合并
    - 数组: 完全替换
    - 基本类型: 直接覆盖
    - parent字段: 跳过
    
    参数:
        base: 基础配置 (父配置)
        override: 覆盖配置 (子配置)
    
    返回:
        合并后的配置
    """
    result = base.copy()
    
    for key, override_value in override.items():
        # 跳过parent字段
        if key == 'parent':
            continue
        
        if key not in result:
            # 新字段，直接添加
            result[key] = override_value
        else:
            base_value = result[key]
            
            # 检查类型并合并
            if isinstance(override_value, dict) and isinstance(base_value, dict):
                # 对象: 递归合并
                result[key] = deep_merge(base_value, override_value)
            else:
                # 数组、基本类型、null: 直接覆盖
                result[key] = override_value
    
    return result
```

### 2.2 复杂度分析

- **时间复杂度**: O(n × m)，其中 n 是配置键的总数，m 是嵌套深度
- **空间复杂度**: O(n × m)，需要存储合并后的结果

---

## 3. 递归加载配置算法

### 3.1 伪代码

```python
def load_config_with_inheritance(
    file_path: str,
    visited: set = None,
    root_dir: str = None
) -> dict:
    """
    递归加载配置及其父配置
    
    参数:
        file_path: 配置文件路径
        visited: 已访问的文件集合 (用于循环检测)
        root_dir: 配置根目录
    
    返回:
        完全合并后的配置
    
    异常:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON解析失败
        CircularInheritanceError: 循环继承
    """
    # 初始化
    if visited is None:
        visited = set()
    
    if root_dir is None:
        root_dir = get_config_root_dir()
    
    # 规范化路径
    abs_path = os.path.abspath(file_path)
    
    # 循环检测
    if abs_path in visited:
        chain = list(visited) + [abs_path]
        raise CircularInheritanceError(chain)
    
    # 标记为已访问
    visited.add(abs_path)
    
    # 读取配置文件
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Config file not found: {abs_path}")
    
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigParseError(f"Invalid JSON in {abs_path}: {e}")
    
    # 检查是否有parent字段
    if 'parent' not in config:
        # 无parent，返回当前配置
        return config
    
    # 解析父配置路径
    parent_path = resolve_parent_path(abs_path, config['parent'], root_dir)
    
    # 递归加载父配置
    parent_config = load_config_with_inheritance(
        parent_path,
        visited.copy(),  # 复制visited集合，避免不同分支互相影响
        root_dir
    )
    
    # 合并配置 (父 <- 子)
    merged_config = deep_merge(parent_config, config)
    
    return merged_config
```

### 3.2 复杂度分析

- **时间复杂度**: O(d × n × m)，其中 d 是继承深度，n 是配置键数量，m 是嵌套深度
- **空间复杂度**: O(d × n × m)，递归栈和配置数据

---

## 4. 路径解析算法

### 4.1 伪代码

```python
def resolve_parent_path(
    current_file: str,
    parent_path: str,
    root_dir: str
) -> str:
    """
    解析parent路径为绝对路径
    
    参数:
        current_file: 当前配置文件的绝对路径
        parent_path: parent字段的值
        root_dir: 配置根目录
    
    返回:
        父配置文件的绝对路径
    
    异常:
        InvalidPathError: 非法路径
    """
    # 安全检查：禁止绝对系统路径
    if parent_path.startswith('/') or (len(parent_path) > 1 and parent_path[1] == ':'):
        raise InvalidPathError(f"Absolute system paths are not allowed: {parent_path}")
    
    # 判断是相对路径还是绝对路径（相对于配置根目录）
    if parent_path.startswith('./') or parent_path.startswith('../'):
        # 相对路径：相对于当前文件所在目录
        current_dir = os.path.dirname(current_file)
        resolved_path = os.path.normpath(os.path.join(current_dir, parent_path))
    else:
        # 绝对路径：相对于配置根目录
        resolved_path = os.path.normpath(os.path.join(root_dir, parent_path))
    
    # 安全检查：确保路径在配置根目录内
    if not resolved_path.startswith(root_dir):
        raise InvalidPathError(
            f"Parent path escapes config root directory: {parent_path} "
            f"(resolved to {resolved_path})"
        )
    
    return resolved_path
```

### 4.2 安全考虑

- 禁止绝对系统路径（如 `/etc/passwd`, `C:\Windows\System32`）
- 禁止路径穿越（如 `../../../etc/passwd`）
- 所有路径必须在配置根目录内

---

## 5. 提取进程配置算法

### 5.1 伪代码

```python
def extract_process_config(
    config: dict,
    process_type: str = None,
    process_id: int = None
) -> dict:
    """
    从完整配置中提取指定进程的最终配置
    
    合并顺序: common -> processType -> processType_processId
    
    参数:
        config: 完整配置
        process_type: 进程类型 (如 'logic', 'dbmgr', 'router')
        process_id: 进程实例ID (如 1, 2, 3)
    
    返回:
        进程的最终配置
    """
    result = {}
    
    # 步骤1: 合并 common
    if 'common' in config:
        result = deep_merge(result, config['common'])
    
    # 步骤2: 合并进程类型配置
    if process_type and process_type in config:
        result = deep_merge(result, config[process_type])
    
    # 步骤3: 合并具体进程实例配置
    if process_type and process_id:
        process_key = f"{process_type}_{process_id}"
        if process_key in config:
            result = deep_merge(result, config[process_key])
    
    return result
```

### 5.2 示例

**输入**:
```python
config = {
    "common": {"logLevel": "warn", "namespace": "c7_test"},
    "logic": {"logLevel": "info", "database": "c7_test"},
    "logic_1": {"logLevel": "debug", "ip": "127.0.0.1"}
}

extract_process_config(config, 'logic', 1)
```

**输出**:
```python
{
    "logLevel": "debug",       # 来自 logic_1
    "namespace": "c7_test",    # 来自 common
    "database": "c7_test",     # 来自 logic
    "ip": "127.0.0.1"          # 来自 logic_1
}
```

---

## 6. 缓存管理算法

### 6.1 缓存Key生成

```python
def generate_cache_key(
    env: str,
    branch_type: str = 'mainline',
    process_type: str = None,
    process_id: int = None
) -> str:
    """
    生成唯一的缓存key
    
    格式: config_{env}_{branch}[_{processType}[_{processId}]]
    """
    parts = ['config', env, branch_type]
    
    if process_type:
        parts.append(process_type)
    
    if process_id:
        parts.append(str(process_id))
    
    return '_'.join(parts)
```

### 6.2 缓存有效性检查

```python
def is_cache_valid(cache_entry: dict, p4_path: str) -> bool:
    """
    检查缓存是否有效
    
    有效条件:
    1. 缓存存在
    2. changelist匹配
    3. 未超过TTL (可选)
    """
    if not cache_entry:
        return False
    
    # 检查changelist
    cached_cl = cache_entry.get('changelist', 0)
    latest_cl = p4Utils.get_latest_changelist(p4_path)
    
    if cached_cl != latest_cl:
        return False
    
    # 检查TTL (可选)
    if 'ttl' in cache_entry:
        age = time.time() - cache_entry.get('timestamp', 0)
        if age > cache_entry['ttl']:
            return False
    
    return True
```

---

## 7. P4文件同步算法

### 7.1 伪代码

```python
def sync_p4_file(
    p4_path: str,
    local_path: str,
    force: bool = False
) -> bool:
    """
    从P4同步文件到本地
    
    参数:
        p4_path: P4路径 (如 //C7/Development/Mainline/...)
        local_path: 本地路径
        force: 是否强制同步 (忽略本地修改)
    
    返回:
        同步是否成功
    """
    try:
        # 确保本地目录存在
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # 调用P4工具同步文件
        ret = p4Utils.update_file(
            p4_path,
            local_path,
            force=force,
            changelist=0  # 0表示最新版本
        )
        
        if not ret:
            raise P4SyncError(f"Failed to sync: {p4_path}")
        
        return True
    
    except Exception as e:
        app.logger.error(f"P4 sync error: {p4_path} -> {e}")
        return False
```

---

## 8. 完整API实现

### 8.1 主流程

```python
@app.route('/getConfig', methods=['GET'])
def getConfig():
    """
    获取配置接口
    
    参数:
        env: 环境名称 (必选)
        branchType: 分支类型 (可选, 默认 'mainline')
        processType: 进程类型 (可选)
        processId: 进程ID (可选)
        syncP4: 是否强制同步 (可选, 默认 false)
    
    返回:
        配置JSON
    """
    try:
        # 1. 参数解析
        env = request.args.get('env')
        if not env:
            return jsonify({'errMsg': 'Missing required parameter: env'}), 400
        
        branch_type = request.args.get('branchType', 'mainline')
        process_type = request.args.get('processType')
        process_id = int(request.args.get('processId')) if request.args.get('processId') else None
        sync_p4 = parse_bool(request.args.get('syncP4'), default=False)
        
        # 2. 路径构建
        p4_path, local_path = build_config_path(env, branch_type)
        
        # 3. 缓存检查
        cache_key = generate_cache_key(env, branch_type, process_type, process_id)
        
        if not sync_p4:
            cached_result = get_cached_config(cache_key, p4_path)
            if cached_result:
                return jsonify(cached_result)
        
        # 4. P4同步
        if sync_p4 or not os.path.exists(local_path):
            if not sync_p4_file(p4_path, local_path, force=sync_p4):
                return jsonify({'errMsg': f'Failed to sync: {p4_path}'}), 500
        
        # 5. 加载配置
        config = load_config_with_inheritance(local_path)
        
        # 6. 提取进程配置
        if process_type:
            config_data = extract_process_config(config, process_type, process_id)
        else:
            config_data = config
        
        # 7. 获取changelist
        changelist = p4Utils.get_latest_changelist(p4_path) or 0
        p4_path_at_cl = f"{p4_path}@{changelist}" if changelist > 0 else p4_path
        
        # 8. 组装结果
        result = {
            'env': env,
            'branchType': branch_type,
            'configP4Path': p4_path,
            'configP4PathAtCL': p4_path_at_cl,
            'configChangelist': changelist,
            'data': config_data
        }
        
        if process_type:
            result['processType'] = process_type
            if process_id:
                result['processId'] = process_id
        
        # 9. 缓存结果
        cache_config_result(cache_key, p4_path, result, changelist)
        
        # 10. 返回响应
        return jsonify(result)
    
    except Exception as e:
        context = {
            'env': env,
            'branchType': branch_type,
            'p4Path': p4_path,
            'localPath': local_path
        }
        return handle_config_error(e, context)
```

---

## 9. 时间复杂度总结

| 操作 | 时间复杂度 | 说明 |
|------|-----------|------|
| 路径解析 | O(1) | 字符串操作 |
| 读取文件 | O(n) | n为文件大小 |
| JSON解析 | O(n) | n为JSON大小 |
| 深度合并 | O(n × m) | n为键数量，m为嵌套深度 |
| 递归加载 | O(d × n × m) | d为继承深度 |
| 提取进程配置 | O(n × m) | 3次深度合并 |
| 缓存查询 | O(1) | 字典查询 |
| P4同步 | O(s) | s为网络传输时间 |

**整体复杂度**: O(d × n × m + s)

---

## 10. 空间复杂度总结

| 数据结构 | 空间复杂度 | 说明 |
|---------|-----------|------|
| 配置数据 | O(n × m) | n为键数量，m为嵌套深度 |
| 递归栈 | O(d) | d为继承深度 |
| 缓存 | O(k × n × m) | k为缓存条目数 |
| visited集合 | O(d) | 循环检测 |

**整体空间**: O((k + d) × n × m)

---

## 11. 优化建议

### 11.1 性能优化

1. **缓存预热**: 启动时预加载常用配置
2. **增量同步**: 只同步变更的文件
3. **并行加载**: 对于独立的配置文件，可并行加载
4. **惰性加载**: 只加载请求的进程配置，不加载整个文件

### 11.2 可靠性优化

1. **重试机制**: P4同步失败时自动重试
2. **降级策略**: P4不可用时使用缓存
3. **健康检查**: 定期检查P4连接状态
4. **日志审计**: 记录所有配置访问和错误

### 11.3 可维护性优化

1. **单元测试**: 对每个算法编写测试用例
2. **文档同步**: 代码与文档保持一致
3. **版本管理**: 配置文件版本化管理
4. **监控告警**: 配置加载失败时告警

---

## 12. 测试用例

### 12.1 deep_merge测试

```python
def test_deep_merge():
    # 测试1: 对象合并
    base = {'a': 1, 'b': {'c': 2}}
    override = {'b': {'d': 3}, 'e': 4}
    result = deep_merge(base, override)
    assert result == {'a': 1, 'b': {'c': 2, 'd': 3}, 'e': 4}
    
    # 测试2: 数组替换
    base = {'arr': [1, 2, 3]}
    override = {'arr': [4, 5]}
    result = deep_merge(base, override)
    assert result == {'arr': [4, 5]}
    
    # 测试3: null覆盖
    base = {'key': 'value'}
    override = {'key': None}
    result = deep_merge(base, override)
    assert result == {'key': None}
```

### 12.2 循环继承测试

```python
def test_circular_inheritance():
    # 准备循环引用的配置文件
    # file_a.json -> file_b.json -> file_a.json
    
    with pytest.raises(CircularInheritanceError) as exc_info:
        load_config_with_inheritance('file_a.json')
    
    assert 'file_a.json' in str(exc_info.value)
    assert 'file_b.json' in str(exc_info.value)
```

### 12.3 进程配置提取测试

```python
def test_extract_process_config():
    config = {
        'common': {'a': 1, 'b': 2},
        'logic': {'b': 3, 'c': 4},
        'logic_1': {'c': 5, 'd': 6}
    }
    
    result = extract_process_config(config, 'logic', 1)
    assert result == {'a': 1, 'b': 3, 'c': 5, 'd': 6}
```
