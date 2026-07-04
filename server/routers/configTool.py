"""
Config Tool Router
用于获取和解析C7服务器配置文件
"""

from flask import request, jsonify
import json
import os
import time
from server import app, config
from server.utils import p4Utils

# 配置缓存 (内存缓存)
config_cache = {}

# 配置根目录
CONFIG_ROOT_DIR = config.P4_WORKSPACE_DIRECTORY + "C7/Development/Mainline/Server/config/"


class ConfigError(Exception):
    """配置系统基础异常类"""
    pass


class CircularInheritanceError(ConfigError):
    """循环继承错误"""
    def __init__(self, chain: list):
        self.chain = chain
        self.chain_str = ' -> '.join([os.path.basename(f) for f in chain])
        super().__init__(f"Circular inheritance: {self.chain_str}")


class P4SyncError(ConfigError):
    """P4同步错误"""
    pass


class ConfigParseError(ConfigError):
    """配置解析错误"""
    pass


class InvalidPathError(ConfigError):
    """非法路径错误"""
    pass


def _parse_bool(value, default=False):
    """解析布尔值参数"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in ('true', '1', 'yes')


def deep_merge(base: dict, override: dict) -> dict:
    """
    深度合并两个字典
    
    规则:
    - 对象: 递归合并
    - 数组: 完全替换
    - 基本类型: 直接覆盖
    - parent字段: 跳过
    
    Args:
        base: 基础配置 (父配置)
        override: 覆盖配置 (子配置)
    
    Returns:
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


def resolve_parent_path(current_file: str, parent_path: str, root_dir: str = CONFIG_ROOT_DIR) -> str:
    """
    解析parent路径为绝对路径
    
    Args:
        current_file: 当前配置文件的绝对路径
        parent_path: parent字段的值
        root_dir: 配置根目录
    
    Returns:
        父配置文件的绝对路径
    
    Raises:
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
    
    # 规范化路径分隔符（Windows兼容）
    resolved_path = resolved_path.replace('\\', '/')
    root_dir_norm = root_dir.replace('\\', '/')
    
    # 安全检查：确保路径在配置根目录内
    if not resolved_path.startswith(root_dir_norm):
        raise InvalidPathError(
            f"Parent path escapes config root directory: {parent_path} "
            f"(resolved to {resolved_path})"
        )
    
    return resolved_path


def load_config_with_inheritance(file_path: str, visited: set = None, root_dir: str = CONFIG_ROOT_DIR) -> dict:
    """
    递归加载配置及其父配置
    
    Args:
        file_path: 配置文件路径
        visited: 已访问的文件集合 (用于循环检测)
        root_dir: 配置根目录
    
    Returns:
        完全合并后的配置
    
    Raises:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON解析失败
        CircularInheritanceError: 循环继承
    """
    # 初始化
    if visited is None:
        visited = set()
    
    # 规范化路径
    abs_path = os.path.abspath(file_path).replace('\\', '/')
    
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
            config_obj = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigParseError(f"Invalid JSON in {abs_path}: {e}")
    
    # 检查是否有parent字段
    if 'parent' not in config_obj:
        # 无parent，返回当前配置
        return config_obj
    
    # 解析父配置路径
    parent_path = resolve_parent_path(abs_path, config_obj['parent'], root_dir)
    
    # 递归加载父配置
    parent_config = load_config_with_inheritance(parent_path, visited.copy(), root_dir)
    
    # 合并配置 (父 <- 子)
    merged_config = deep_merge(parent_config, config_obj)
    
    return merged_config


def extract_process_config(config_obj: dict, process_type: str = None, process_id: int = None) -> dict:
    """
    从完整配置中提取指定进程的最终配置
    
    合并顺序: common -> processType -> processType_processId
    
    Args:
        config_obj: 完整配置
        process_type: 进程类型 (如 'logic', 'dbmgr', 'router')
        process_id: 进程实例ID (如 1, 2, 3)
    
    Returns:
        进程的最终配置
    """
    result = {}
    
    # 步骤1: 合并 common
    if 'common' in config_obj:
        result = deep_merge(result, config_obj['common'])
    
    # 步骤2: 合并进程类型配置
    if process_type and process_type in config_obj:
        result = deep_merge(result, config_obj[process_type])
    
    # 步骤3: 合并具体进程实例配置
    if process_type and process_id:
        process_key = f"{process_type}_{process_id}"
        if process_key in config_obj:
            result = deep_merge(result, config_obj[process_key])
    
    return result


def generate_cache_key(env: str, branch_type: str = 'mainline', 
                       process_type: str = None, process_id: int = None) -> str:
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


def build_config_path(env: str, branch_type: str = 'mainline') -> tuple:
    """
    构建P4路径和本地路径
    
    Args:
        env: 环境名称
        branch_type: 分支类型 ('mainline', 'weekly', 'preonline')
    
    Returns:
        (p4_path, local_path)
    """
    # 确定子目录 (production 或 local)
    if env.startswith('c7_dev') or env.startswith('c7_qa'):
        sub_dir = 'local'
    else:
        sub_dir = 'production'
    
    # 构建P4路径
    if branch_type == 'weekly':
        p4_path = f"//C7/Development/Weekly/Server/config/{sub_dir}/{env}.json"
    elif branch_type == 'preonline':
        p4_path = f"//C7/Release/Preonline/Server/config/{sub_dir}/{env}.json"
    else:  # mainline
        p4_path = f"//C7/Development/Mainline/Server/config/{sub_dir}/{env}.json"
    
    # 构建本地路径
    local_path = os.path.join(config.P4_WORKSPACE_DIRECTORY, p4_path.replace("//", ""))
    
    return p4_path, local_path


def get_cached_config(cache_key: str, p4_path: str) -> dict:
    """
    获取缓存的配置
    
    Returns:
        缓存的配置，如果缓存无效则返回None
    """
    if cache_key not in config_cache:
        return None
    
    cached_data = config_cache[cache_key]
    cached_cl = cached_data.get('changelist', 0)
    
    # 获取P4最新changelist
    try:
        latest_cl = int(p4Utils.get_latest_changelist(p4_path) or 0)
    except Exception as e:
        app.logger.error(f"Failed to get latest changelist for {p4_path}: {e}")
        return None
    
    if cached_cl == latest_cl:
        app.logger.info(f"Cache hit for {cache_key} @ CL {latest_cl}")
        return cached_data['result']
    else:
        app.logger.info(f"Cache stale: cached CL {cached_cl}, latest CL {latest_cl}")
        return None


def cache_config_result(cache_key: str, p4_path: str, result: dict, changelist: int):
    """
    缓存配置结果
    """
    config_cache[cache_key] = {
        'result': result,
        'changelist': changelist,
        'timestamp': time.time()
    }
    
    app.logger.info(f"Cached config {cache_key} @ CL {changelist}")


def handle_config_error(e: Exception, context: dict) -> tuple:
    """
    统一错误处理函数
    
    Returns:
        (response_json, status_code)
    """
    if isinstance(e, FileNotFoundError):
        return jsonify({
            'errMsg': 'Config file not found',
            'file': str(e),
            'p4Path': context.get('p4Path'),
            'localPath': context.get('localPath'),
            'suggestion': 'Check if the file exists in P4 or if the environment name is correct'
        }), 404
    
    elif isinstance(e, json.JSONDecodeError):
        return jsonify({
            'errMsg': 'Invalid JSON format in config file',
            'file': context.get('localPath'),
            'error': str(e),
            'line': e.lineno,
            'column': e.colno,
            'suggestion': 'Fix JSON syntax errors using a JSON validator'
        }), 400
    
    elif isinstance(e, CircularInheritanceError):
        return jsonify({
            'errMsg': 'Circular inheritance detected in config files',
            'inheritanceChain': e.chain_str,
            'files': [os.path.basename(f) for f in e.chain],
            'suggestion': 'Remove circular references from the parent fields'
        }), 400
    
    elif isinstance(e, InvalidPathError):
        return jsonify({
            'errMsg': 'Invalid parent path',
            'error': str(e),
            'suggestion': 'Parent paths must be within the config directory'
        }), 400
    
    elif isinstance(e, P4SyncError):
        return jsonify({
            'errMsg': 'Failed to sync config from P4',
            'p4Path': context.get('p4Path'),
            'error': str(e),
            'suggestion': 'Check P4 connection, permissions, or file availability'
        }), 500
    
    else:
        # 未知错误
        app.logger.error(f"Unexpected config error: {e}", exc_info=True)
        return jsonify({
            'errMsg': 'Internal server error',
            'error': str(e),
            'type': type(e).__name__,
            'suggestion': 'Contact system administrator'
        }), 500


@app.route('/getConfig', methods=['GET'])
def getConfig():
    """
    获取配置接口
    
    参数:
        env: 环境名称 (必选)
        branchType: 分支类型 (可选, 默认 'mainline')
        processType: 进程类型 (可选, 如 'logic', 'dbmgr', 'router')
        processId: 进程ID (可选, 如 1, 2, 3)
        syncP4: 是否强制同步P4 (可选, 默认 false)
    
    返回:
        配置JSON
    """
    app.logger.info("getConfig")
    
    env = None
    branch_type = 'mainline'
    p4_path = None
    local_path = None
    
    try:
        # 1. 参数解析
        env = request.args.get('env')
        if not env:
            return jsonify({
                'errMsg': 'Missing required parameter: env',
                'example': '/getConfig?env=c7_partner&syncP4=false'
            }), 400
        
        branch_type = request.args.get('branchType', 'mainline')
        if branch_type not in ('mainline', 'weekly', 'preonline'):
            return jsonify({
                'errMsg': 'Invalid branchType',
                'providedValue': branch_type,
                'allowedValues': ['mainline', 'weekly', 'preonline']
            }), 400
        
        process_type = request.args.get('processType')
        process_id_str = request.args.get('processId')
        process_id = None
        
        if process_id_str:
            try:
                process_id = int(process_id_str)
                if process_id <= 0:
                    raise ValueError("processId must be positive")
            except ValueError as e:
                return jsonify({
                    'errMsg': 'Invalid processId',
                    'providedValue': process_id_str,
                    'error': str(e),
                    'suggestion': 'processId must be a positive integer'
                }), 400
        
        sync_p4 = _parse_bool(request.args.get('syncP4'), default=False)
        
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
            app.logger.info(f"Syncing config from P4: {p4_path}")
            ret = p4Utils.update_file(p4_path, local_path, force=True, changelist=0)
            if not ret:
                raise P4SyncError(f"Failed to sync: {p4_path}")
        
        # 5. 加载配置
        app.logger.info(f"Loading config: {local_path}")
        config_obj = load_config_with_inheritance(local_path)
        
        # 6. 提取进程配置
        if process_type:
            config_data = extract_process_config(config_obj, process_type, process_id)
        else:
            config_data = config_obj
        
        # 7. 获取changelist
        try:
            changelist = int(p4Utils.get_latest_changelist(p4_path) or 0)
            p4_path_at_cl = f"{p4_path.split('#')[0].split('@')[0]}@{changelist}" if changelist > 0 else p4_path
        except Exception as e:
            app.logger.error(f"Failed to get changelist: {e}")
            changelist = 0
            p4_path_at_cl = p4_path
        
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


@app.route('/clearConfigCache', methods=['POST'])
def clearConfigCache():
    """
    清除配置缓存
    
    参数:
        env: 指定环境 (可选，不指定则清除全部)
        branchType: 指定分支 (可选)
    """
    app.logger.info("clearConfigCache")
    
    env = request.args.get('env')
    branch_type = request.args.get('branchType')
    
    if env:
        # 清除指定环境的缓存
        prefix = f"config_{env}"
        if branch_type:
            prefix += f"_{branch_type}"
        
        keys_to_remove = [k for k in config_cache.keys() if k.startswith(prefix)]
        for key in keys_to_remove:
            del config_cache[key]
        
        app.logger.info(f"Cleared {len(keys_to_remove)} cache entries for {prefix}")
        return jsonify({'message': f'Cleared {len(keys_to_remove)} cache entries', 'prefix': prefix})
    else:
        # 清除全部缓存
        count = len(config_cache)
        config_cache.clear()
        
        app.logger.info(f"Cleared all {count} cache entries")
        return jsonify({'message': f'Cleared all {count} cache entries'})
