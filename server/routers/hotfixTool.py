# 和游戏服务器 战斗相关的route放这个里 这里只放对内的接口 对外的放battleExternal里

# builtin
from datetime import datetime
import os
import uuid
import subprocess
import re
import threading
import time

# 3rd ext
from flask import render_template, request, jsonify, Response
from sqlalchemy import and_
import io
import csv

# int
from appImp import app
from Implement.hotfixImpl import p4Imp
from Implement.hotfixImpl import hotfixImp
from utility import p4Utils
import config
import json
from managers.timeMgr import cron
# region init

# endregion

# 测试环境Jenkins URL
# JENKINS_HOTFIX_STAGING_URL = "https://game-hangzhou-jenkinsc7.test.gifshow.com/view/Server/job/Reload_Server_Weekly/build?delay=0sec"
# 正式环境Jenkins URL
JENKINS_HOTFIX_STAGING_URL = "https://game-hangzhou-jenkinsc7.test.gifshow.com/view/Server/job/Reload_Server_Weekly/build?delay=0sec"
JENKINS_HOTFIX_IDC_URL = "https://game-hangzhou-jenkinsc7.test.gifshow.com/view/Server/job/Reload_Cloud_Weekly/build?delay=0sec"

# ── 索引内存缓存（带 TTL，避免每次请求都读文件）──────────────────────────
_INDEX_CACHE_TTL = 600  # 秒，缓存有效期（10分钟）
_index_cache = {}       # {"{side}/{branch_type}": {"index": dict, "ts": float}}
_index_cache_lock = threading.Lock()

def _get_cached_index(side, branch_type):
    """读取内存缓存的索引,过期返回 None"""
    key = f"{side}/{branch_type}"
    with _index_cache_lock:
        entry = _index_cache.get(key)
        if entry and (time.time() - entry['ts']) < _INDEX_CACHE_TTL:
            app.logger.info(f"_get_cached_index: cache hit for key='{key}', {len(entry['index'])} files, age={time.time() - entry['ts']:.1f}s")
            return entry['index']
        elif entry:
            app.logger.info(f"_get_cached_index: cache expired for key='{key}', age={time.time() - entry['ts']:.1f}s > {_INDEX_CACHE_TTL}s")
        else:
            app.logger.info(f"_get_cached_index: cache miss for key='{key}'")
    return None

def _set_cached_index(side, branch_type, index):
    """写入内存缓存"""
    key = f"{side}/{branch_type}"
    with _index_cache_lock:
        _index_cache[key] = {'index': index, 'ts': time.time()}
        app.logger.info(f"_set_cached_index: cache set for key='{key}', {len(index)} files, ttl={_INDEX_CACHE_TTL}s")

def _invalidate_cached_index(side, branch_type):
    """索引重建后主动失效缓存"""
    key = f"{side}/{branch_type}"
    with _index_cache_lock:
        _index_cache.pop(key, None)


_func_index_building_keys = set()
_func_index_building_lock = threading.Lock()


def _is_func_index_building(side, branch_type):
    key = f"{side}/{branch_type}"
    with _func_index_building_lock:
        return key in _func_index_building_keys


def _mark_func_index_building(side, branch_type, building=True):
    key = f"{side}/{branch_type}"
    with _func_index_building_lock:
        if building:
            _func_index_building_keys.add(key)
        else:
            _func_index_building_keys.discard(key)


def _start_build_index(side, branch_type, force_full=False, notify=True, on_complete=None, notify_user=''):
    if _is_func_index_building(side, branch_type):
        if on_complete:
            on_complete(None)
        return False
    _mark_func_index_building(side, branch_type, True)
    import gevent

    def _worker():
        try:
            from appImp import app as flask_app
            with flask_app.app_context():
                if force_full:
                    result = _build_hotfix_func_index(side, branch_type, notify=notify, force=True)
                    if result is None:
                        return
                    if not result:
                        _notify_build_complete(side, branch_type, '全量构建失败', notify_user)
                        return
                    summary = f"全量构建完成：{len(result)} 文件"
                else:
                    result = _incremental_build_hotfix_func_index(side, branch_type, notify=notify)
                    if not isinstance(result, dict):
                        result = {'files': 0, 'funcs': 0, 'changed': 0, 'message': '未知结果'}
                    if result.get('message', '').startswith('无已有索引'):
                        full_result = _build_hotfix_func_index(side, branch_type, notify=notify, force=True)
                        if full_result is None:
                            return
                        if not full_result:
                            _notify_build_complete(side, branch_type, '全量构建失败', notify_user)
                            return
                        summary = f"全量构建完成：{len(full_result)} 文件"
                    else:
                        summary = result.get('message', '增量构建完成')
                if on_complete:
                    on_complete(result)
                _notify_build_complete(side, branch_type, summary, notify_user)
        except Exception as e:
            app.logger.error(f"_start_build_index error for {side}/{branch_type}: {e}")
            _notify_build_complete(side, branch_type, f"构建失败：{e}", notify_user)
        finally:
            _mark_func_index_building(side, branch_type, False)

    gevent.spawn(_worker)
    return True


def _notify_build_complete(side, branch_type, summary, notify_user=''):
    try:
        msg = f"索引构建完成 ({side}/{branch_type})：{summary}"
        app.logger.info(f"_notify_build_complete: {msg}")
        if notify_user:
            from Implement.hotfixImpl.c7KimRobot import C7KimRobot
            kim = C7KimRobot()
            notify_users = notify_user.split(";")
            for user in notify_users:
                ok, err = kim.send_msg_to_user(user, msg)
                if not ok:
                    app.logger.warning(f"_notify_build_complete: notify {user} failed: {err}")
    except Exception as e:
        app.logger.warning(f"_notify_build_complete failed: {e}")


def _async_build_project_symbol_index(side, branch_type, on_complete=None):
    global _symbol_index_is_building
    def _worker():
        global _symbol_index_is_building
        try:
            from appImp import app as flask_app
            with flask_app.app_context():
                result = _build_project_symbol_index(side, branch_type)
                if on_complete:
                    on_complete(result)
        except Exception as e:
            app.logger.error(f"_async_build_project_symbol_index error for {side}/{branch_type}: {e}")
        finally:
            _symbol_index_is_building = False
    _symbol_index_is_building = True
    import gevent
    gevent.spawn(_worker)

# ── C7 Server 和 Tags 数据缓存（避免重复读文件）───────────────────────────
_C7_DATA_CACHE_TTL = 300  # 秒，缓存有效期（5分钟，因为这些数据变更较少）
_c7_data_cache = {}  # {"c7_server": {"data": dict, "ts": float}, "c7_tags": {...}}
_c7_data_cache_lock = threading.Lock()

def _get_cached_c7_data(data_type):
    """读取 C7 数据缓存，过期返回 None
    
    Args:
        data_type: 'c7_server' 或 'c7_tags'
    """
    with _c7_data_cache_lock:
        entry = _c7_data_cache.get(data_type)
        if entry and (time.time() - entry['ts']) < _C7_DATA_CACHE_TTL:
            return entry['data']
    return None

def _set_cached_c7_data(data_type, data):
    """写入 C7 数据缓存
    
    Args:
        data_type: 'c7_server' 或 'c7_tags'
        data: 要缓存的数据
    """
    with _c7_data_cache_lock:
        _c7_data_cache[data_type] = {'data': data, 'ts': time.time()}

# ── P4 相关数据缓存（基于 changelist 版本校验，保证数据最新）────────────────
_p4_data_cache = {}  # {cache_key: {"data": dict, "changelist": int, "p4_path": str}}
_p4_data_cache_lock = threading.Lock()

def _get_cached_p4_data(cache_key, p4_path=None, skip_cl_check=False):
    """读取 P4 数据缓存，如果 changelist 未变则返回缓存数据
    
    Args:
        cache_key: 缓存键，如 'hotfix_server_weekly' 或 'manifest_server_prod'
        p4_path: P4 文件路径，用于检查最新 changelist（目录路径可能不准确）
        skip_cl_check: 是否跳过 changelist 检查（对于目录类型）
    
    Returns:
        缓存的数据，如果 changelist 已变或不存在缓存则返回 None
    """
    with _p4_data_cache_lock:
        entry = _p4_data_cache.get(cache_key)
        if not entry:
            return None
        
        # 如果跳过检查，直接返回缓存（用于目录列表，在获取数据后对比）
        if skip_cl_check:
            app.logger.debug(f"P4 cache returned (skip_cl_check): {cache_key}")
            return entry
        
        # 快速检查 P4 文件的最新 changelist（只查询 metadata，不下载文件）
        if p4_path:
            try:
                latest_cl = int(p4Utils.get_latest_changelist(p4_path) or 0)
                if latest_cl > 0 and latest_cl == entry.get('changelist', 0):
                    app.logger.debug(f"P4 cache hit: {cache_key} @ CL {latest_cl}")
                    return entry['data']
                else:
                    app.logger.debug(f"P4 cache miss: {cache_key} (cached CL {entry.get('changelist', 0)} vs latest CL {latest_cl})")
            except Exception as e:
                app.logger.warning(f"P4 cache check failed for {cache_key}: {e}")
    
    return None

def _set_cached_p4_data(cache_key, p4_path, data, changelist):
    """写入 P4 数据缓存
    
    Args:
        cache_key: 缓存键
        p4_path: P4 文件路径
        data: 要缓存的数据
        changelist: 当前 changelist 号
    """
    with _p4_data_cache_lock:
        _p4_data_cache[cache_key] = {
            'data': data,
            'changelist': changelist,
            'p4_path': p4_path
        }
        app.logger.debug(f"P4 cache updated: {cache_key} @ CL {changelist}")

def _invalidate_p4_cache(cache_key):
    """清除指定的 P4 缓存"""
    with _p4_data_cache_lock:
        if cache_key in _p4_data_cache:
            del _p4_data_cache[cache_key]
            app.logger.debug(f"P4 cache invalidated: {cache_key}")

# AI Proxy URL: 容器内用 host.docker.internal，宿主机直接运行用 127.0.0.1
# 优先检查 DNS 解析，/.dockerenv 存在但 host.docker.internal 不解析时从路由表获取网关 IP
def _get_proxy_host():
    if not os.path.exists('/.dockerenv'):
        return '127.0.0.1'
    try:
        import socket
        socket.getaddrinfo('host.docker.internal', 19999)
        return 'host.docker.internal'
    except socket.gaierror:
        pass
    # Docker 内 host.docker.internal 不可解析，从 /proc/net/route 读取默认网关 IP
    try:
        with open('/proc/net/route') as f:
            for line in f:
                fields = line.strip().split()
                if len(fields) >= 3 and fields[1] == '00000000':
                    gw_hex = fields[2]
                    if gw_hex != '00000000':
                        gw_bytes = [int(gw_hex[i:i+2], 16) for i in range(6, -1, -2)]
                        return f'{gw_bytes[0]}.{gw_bytes[1]}.{gw_bytes[2]}.{gw_bytes[3]}'
    except Exception:
        pass
    return '172.17.0.1'  # fallback: default docker bridge gateway

_FLICKCLI_PROXY_HOST = _get_proxy_host()
_FLICKCLI_PROXY_URL = f'http://{_FLICKCLI_PROXY_HOST}:19999'

_TAG_RULES = [
    ('/Data/Flowchart/',                                'flowchart'),
    ('/Data/Formula/',                                  'formula'),
    ('/Data/Config/SpaceData/',                         'space'),
    ('/Data/LogicSpaceData/',                           'space'),
    ('/Data/Config/Quest/',                             'quest'),
    ('/Data/Quest/',                                    'quest'),
    ('/Data/Config/BattleSystem/',                      'skill'),
    ('/Data/SkillData/',                                'skill'),
    ('/Data/AnimLib/',                                  'animLib'),
    ('/Data/Excel/',                                    'excel'),
]

# 独立检测的 tag，不受其他规则 break 影响，始终并行判断
_TAG_RULES_INDEPENDENT = [
    ('/Server/',    'server'),
    ('/Client/',    'client'),
]


def _detect_tags_from_file_pairs(hotfixPrepareInfo):
    """根据文件路径检测 hotfix 类型标签"""
    tag_set = []
    seen = set()
    side_tag = None  # client/server 只取第一个出现的
    for pair in hotfixPrepareInfo:
        raw_path = pair.get('rawFilePath', '')
        # 独立规则：client/server 互斥，只保留第一个
        if side_tag is None:
            for pattern, tag in _TAG_RULES_INDEPENDENT:
                if pattern.lower() in raw_path.lower():
                    side_tag = tag
                    break
        # 普通规则：匹配到第一个即停止
        for pattern, tag in _TAG_RULES:
            if pattern.lower() in raw_path.lower():
                if tag not in seen:
                    seen.add(tag)
                    tag_set.append(tag)
                break
    if side_tag:
        tag_set.insert(0, side_tag)
    return tag_set


def _extract_diff_tags(diff_info_list, max_tags=None, display_mode=False):
    """
    从diff_info列表中提取修改类型生成tag，按操作类型聚合
    
    聚合规则：
    - 只按操作类型（delete/modify/add）聚合，不考虑字段名
    - 例如: delete:data.1.IsLockScore, delete:data.2.Name, delete:data.3.Status
      都会聚合成: delete:data.1.IsLockScore;2.Name;3.Status等
    
    参数：
    - max_tags: 最大标签数量限制，None表示不限制
    - display_mode: True=生成显示版本(最多3个路径)，False=生成存储版本(全部路径)
    """
    # 第一步：收集所有diff，只按 diff_type 分组
    groups = {}  # key: diff_type, value: list of items
    
    for raw_info in diff_info_list:
        diff_info = raw_info.get('diff_info', [])
        
        for diff in diff_info:
            diff_type = diff.get('diff_type')  # 'add', 'modify', 'delete'
            path = diff.get('path', [])        # ['data', 1, 'IsLockScore']
            
            if not diff_type or not path:
                continue
            
            # 如果有 tag_paths，说明是长list合并，展开为多个路径用于tag
            tag_path_list = diff.get('tag_paths')
            paths_to_add = tag_path_list if tag_path_list else [path]
            
            for tag_path in paths_to_add:
                # 构建完整路径字符串
                path_parts = []
                last_numeric_id = None
                
                for i, p in enumerate(tag_path):
                    if isinstance(p, str):
                        if '.' in str(p) or ' ' in str(p):
                            path_parts.append(f'"{p}"')
                        else:
                            path_parts.append(p)
                    else:
                        # 数字ID
                        path_parts.append(str(p))
                        last_numeric_id = str(p)
                
                full_path_str = '.'.join(path_parts)
                
                # 分组key：只按操作类型
                group_key = diff_type
                
                if group_key not in groups:
                    groups[group_key] = []
                
                groups[group_key].append({
                    'full_path': full_path_str,
                    'id': last_numeric_id,
                    'path_parts': path_parts
                })
    
    # 第二步：为每个操作类型生成聚合tag
    tags = []
    
    for diff_type, items in groups.items():
        if max_tags and len(tags) >= max_tags:
            break
        
        # 提取所有路径字符串（从第一个数字开始）
        all_path_strs = []
        for item in items:
            if item['id']:
                # 从第一个数字开始到结尾的路径
                parts = item['path_parts']
                for i, part in enumerate(parts):
                    if part.isdigit():
                        all_path_strs.append('.'.join(parts[i:]))
                        break
            else:
                # 没有数字ID，使用完整路径
                all_path_strs.append(item['full_path'])
        
        # 根据模式生成tag
        if display_mode:
            # 显示模式：最多3个路径
            if len(all_path_strs) <= 3:
                path_part = ';'.join(all_path_strs)
            else:
                path_part = ';'.join(all_path_strs[:3]) + '等'
        else:
            # 存储模式：全部路径
            path_part = ';'.join(all_path_strs)
        
        # 构建最终tag
        if all_path_strs:
            # 检查是否有data前缀
            has_data_prefix = any(item['full_path'].startswith('data.') for item in items)
            prefix = 'data.' if has_data_prefix else ''
            tag = f"{diff_type}:{prefix}{path_part}"
        else:
            tag = f"{diff_type}:unknown"
        
        # 限制tag长度（仅在显示模式）
        if display_mode and len(tag) > 200:
            tag = tag[:197] + '...'
        
        tags.append(tag)
    
    return tags


def _extract_content_tags(diff_info_list):
    """
    从 diffInfo 列表中提取内容标签，格式为 <prefix>_<id>
    
    规则：
    - excel/skill 等：取 table_name 为前缀，path[1]（data.后第一段）为 ID
    - spacedata：取 raw_file_path 文件名（不含扩展名）作为标签，如 5200002
    - flowchart 等无 table_name 且无 raw_file_path 的类型跳过
    - 去重后返回
    """
    import os as _os
    seen = set()
    tags = []
    for item in diff_info_list:
        table_name = item.get('table_name')
        raw_file_path = item.get('raw_file_path')

        if table_name:
            # formula：有 table_name 但只有 code_diff_info，从函数名提取标签
            if item.get('code_diff_info') is not None:
                code_diff_info = item.get('code_diff_info', [])
                if code_diff_info:
                    for diff in code_diff_info:
                        func_name = diff.get('name', '')
                        if func_name:
                            tag = f"formula_{func_name}"
                            if tag not in seen:
                                seen.add(tag)
                                tags.append(tag)
                else:
                    # diff 为空（无变化），回退用文件名
                    tag = f"formula_{table_name}"
                    if tag not in seen:
                        seen.add(tag)
                        tags.append(tag)
                continue
            # excel/skill/quest/animlib 等有 table_name 且有 diff_info 的类型
            # 从 raw_file_path 推断类型前缀（用于纯数字 table_name 或纯数字 row_id）
            raw_fp = item.get('raw_file_path', '')
            type_prefix = None
            if raw_fp:
                _TYPE_PATH_RULES = [
                    ('/SkillData/', 'skill'),
                    ('/Skill/', 'skill'),
                    ('/EffectSkill/', 'skill'),
                    ('/BattleSystem/', 'skill'),
                    ('/SpaceData/', 'space'),
                    ('/LogicSpaceData/', 'space'),
                    ('/Quest/', 'quest'),
                    ('/Excel/', 'excel'),
                    ('/AnimLib/', 'animLib'),
                ]
                for pattern, prefix in _TYPE_PATH_RULES:
                    if pattern.lower() in raw_fp.lower():
                        type_prefix = prefix
                        break
            
            diff_info = item.get('diff_info', [])
            for diff in diff_info:
                path = diff.get('path', [])
                if not path:
                    continue
                if path[0] == 'data':
                    if len(path) < 2:
                        continue
                    row_id = str(path[1])
                else:
                    row_id = str(path[0])
                
                # 标签格式规则：
                # 1. table_name 是纯数字 → 类型_table_name_row_id
                # 2. row_id 是纯数字且有类型前缀 → 类型_table_name_row_id
                # 3. 其他 → table_name_row_id
                if type_prefix and (table_name.isdigit() or row_id.isdigit()):
                    tag = f"{type_prefix}_{table_name}_{row_id}"
                else:
                    tag = f"{table_name}_{row_id}"
                if tag not in seen:
                    seen.add(tag)
                    tags.append(tag)
        elif raw_file_path:
            # spacedata：从文件路径提取文件名（不含扩展名），加 space_ 前缀，如 space_5200002
            file_name = _os.path.splitext(_os.path.basename(raw_file_path))[0]
            if file_name:
                tag = f"space_{file_name}"
                if tag not in seen:
                    seen.add(tag)
                    tags.append(tag)
        else:
            # flowchart：用 file_name 字段（如 Flowchart_AI_MinDragon_AI）
            file_name = item.get('file_name')
            if file_name:
                tag = f"flowchart_{file_name}"
                if tag not in seen:
                    seen.add(tag)
                    tags.append(tag)
        # flowchart 等跳过
    return tags


# region hotfix type classification for code review
# Hotfix Code Review 类型分类常量
_HOTFIX_TYPE_FUNC_MOD = 'func_mod'    # 修改函数
_HOTFIX_TYPE_DATA_MOD = 'data_mod'    # 修改数据
_HOTFIX_TYPE_OTHER = 'other'          # 其他（调用接口、配置变更等）

_HOTFIX_TYPE_DISPLAY = {
    _HOTFIX_TYPE_FUNC_MOD: '修改函数',
    _HOTFIX_TYPE_DATA_MOD: '修改数据',
    _HOTFIX_TYPE_OTHER: '其他',
}

def _classify_hotfix_type(lua_content):
    """
    根据 hotfix lua 文件内容分类 hotfix 类型

    三种类型：
    - func_mod: 修改函数，包含 ClassName.MethodName = function(...) 模式
    - data_mod: 修改数据，包含 getHotfixRowData 或类似数据修改模式
    - other: 其他，调用接口、配置变更等

    Args:
        lua_content: hotfix lua 文件的文本内容

    Returns: dict
        {
            'type': 'func_mod' | 'data_mod' | 'other',
            'type_display': '修改函数' | '修改数据' | '其他',
            'func_names': [...],       # func_mod 时有效
            'table_names': [...],      # data_mod 时有效
            'field_names': [...],      # data_mod 时有效
            'description': '...',      # other 时有效
        }
    """
    lines = lua_content.strip().split('\n')

    # 检测 func_mod：复用 AST 提取逻辑，支持多种写法
    # - A.B = function(...)
    # - function A.B(...) / function A:B(...)
    # - HotfixComponentFunction("A", "B", ...) 含动态参数
    func_names = _extract_func_names_from_lua(lua_content)

    if func_names:
        return {
            'type': _HOTFIX_TYPE_FUNC_MOD,
            'type_display': _HOTFIX_TYPE_DISPLAY[_HOTFIX_TYPE_FUNC_MOD],
            'func_names': func_names,
            'table_names': [],
            'field_names': [],
            'description': '',
        }

    # 检测 data_mod：getHotfixRowData('TableName', rowId, ...) 和 tableRowData_XXX.FieldName = value
    data_mod_pattern = re.compile(r"getHotfixRowData\s*\(\s*'(\w+)'")
    table_row_pattern = re.compile(r'(tableRowData_\w+)\.(\w+)\s*=\s*')
    excel_print_pattern = re.compile(r'(?:client|server)\s+excel\s+hotfix\s+(\w+)\s+start')

    table_names = set()
    field_names = []

    for line in lines:
        match = data_mod_pattern.search(line)
        if match:
            table_names.add(match.group(1))
        match = table_row_pattern.search(line.strip())
        if match:
            field_names.append(match.group(2))
        match = excel_print_pattern.search(line)
        if match:
            table_names.add(match.group(1))

    if table_names or field_names:
        return {
            'type': _HOTFIX_TYPE_DATA_MOD,
            'type_display': _HOTFIX_TYPE_DISPLAY[_HOTFIX_TYPE_DATA_MOD],
            'func_names': [],
            'table_names': list(table_names),
            'field_names': list(set(field_names)),
            'description': '',
        }

    # Default: other
    description = ''
    desc_print_pattern = re.compile(r'print\s*\(\s*["\'](.{3,})["\']\s*\)')
    comment_pattern = re.compile(r'^--\s*(.{3,})')
    for line in lines:
        stripped = line.strip()
        match = desc_print_pattern.search(stripped)
        if match:
            description = match.group(1).strip()
            break
        match = comment_pattern.match(stripped)
        if match:
            description = match.group(1).strip()
            break

    return {
        'type': _HOTFIX_TYPE_OTHER,
        'type_display': _HOTFIX_TYPE_DISPLAY[_HOTFIX_TYPE_OTHER],
        'func_names': [],
        'table_names': [],
        'field_names': [],
        'description': description,
    }


def _generate_hotfix_type_tags(lua_content, side=None):
    """
    根据 hotfix lua 文件内容生成类型标签（用于 Manifest Code Review 展示）

    Args:
        lua_content: hotfix lua 文件的文本内容
        side: 'client' | 'server' | None，可选的端侧标签

    Returns: list of tag strings
    """
    classify_result = _classify_hotfix_type(lua_content)
    hotfix_type = classify_result['type']
    tags = []

    if side:
        tags.append(side)

    tags.append(classify_result['type_display'])

    if hotfix_type == _HOTFIX_TYPE_FUNC_MOD:
        for func_name in classify_result['func_names']:
            tags.append(f"函数:{func_name}")

    elif hotfix_type == _HOTFIX_TYPE_DATA_MOD:
        for table_name in classify_result['table_names']:
            tags.append(f"表:{table_name}")
        field_names = classify_result['field_names']
        if field_names:
            if len(field_names) <= 3:
                tags.append(f"字段:{','.join(sorted(field_names))}")
            else:
                tags.append(f"字段:{','.join(sorted(field_names[:3]))}等")

    elif hotfix_type == _HOTFIX_TYPE_OTHER:
        if classify_result['description']:
            desc = classify_result['description']
            if len(desc) > 50:
                desc = desc[:47] + '...'
            tags.append(f"说明:{desc}")

    return tags


def _extract_func_names_from_lua(lua_content, file_name='unknown'):
    """委托给 hotfixFuncExtractor，含 AST → AI → 正则 三层 fallback"""
    from Implement.hotfixImpl.hotfixFuncExtractor import extract_func_names as _fe
    return _fe(lua_content, file_name=file_name, ext_logger=app.logger)


def _extract_func_names_with_ai_fallback(lua_content, file_name='unknown'):
    """委托给 hotfixFuncExtractor"""
    from Implement.hotfixImpl.hotfixFuncExtractor import extract_func_names_with_ai_fallback as _ai
    return _ai(lua_content, file_name=file_name, ext_logger=app.logger)


# region Lua 代码蒸馏（Phase 3）

def _distill_func_mod(lines):
    """
    func_mod 蒸馏：保留完整函数体，只合并连续空行

    func_mod 类型不删减逻辑代码，因为 bug 往往藏在细节里。
    只做最轻量的压缩：连续空行合并为 1 行。

    Args:
        lines: list of str, lua 文件的每行内容（不含换行符）

    Returns: list of str, 蒸馏后的行列表
    """
    result = []
    prev_blank = False
    for line in lines:
        is_blank = line.strip() == ''
        if is_blank and prev_blank:
            continue  # 跳过连续空行，只保留第一个
        result.append(line)
        prev_blank = is_blank
    return result


def _distill_data_mod(lines):
    """
    data_mod 蒸馏：只保留关键赋值行，去除中间变量声明、注释和调试 print

    保留规则：
    - getHotfixRowData 行（数据获取入口）
    - tableRowData_xxx.Field = value 行（字段赋值）
    - excel hotfix 标记 print 行（含 "client/server excel hotfix" 的 print）
    - 非 local 的关键行（如 return、if 条件等）
    - end 关键行

    去除规则：
    - 独立注释行（-- 开头）
    - 调试 print 行（非 excel hotfix 标记的 print）
    - 中间 local 变量声明行（local xxx = ... 但不是 getHotfixRowData 的声明）
    - 空行

    Args:
        lines: list of str, lua 文件的每行内容

    Returns: list of str, 蒸馏后的行列表
    """
    result = []
    # 关键模式
    get_hotfix_row_pattern = re.compile(r'getHotfixRowData\s*\(')
    table_row_assign_pattern = re.compile(r'tableRowData_\w+\.\w+\s*=\s*')
    excel_print_pattern = re.compile(r'print\s*\(\s*["\'].*(?:client|server)\s+excel\s+hotfix')
    local_var_pattern = re.compile(r'^\s*local\s+\w+\s*=\s*')

    for line in lines:
        stripped = line.strip()

        # 去除空行
        if stripped == '':
            continue

        # 去除独立注释行
        if stripped.startswith('--'):
            continue

        # 去除调试 print（保留 excel hotfix 标记 print）
        if stripped.startswith('print'):
            if excel_print_pattern.search(stripped):
                result.append(line)  # 保留 excel hotfix 标记 print
            continue  # 去除其他 print

        # 去除中间 local 变量声明（保留 getHotfixRowData 的 local）
        if local_var_pattern.match(stripped):
            if get_hotfix_row_pattern.search(stripped):
                result.append(line)  # 保留 getHotfixRowData 的 local 声明
            continue  # 去除其他 local 声明

        # 保留所有关键行
        result.append(line)

    return result


def _distill_other(lines):
    """
    other 蒸馏：去除空行和独立注释行，保留所有调用语句

    other 类型通常只有几行调用代码，蒸馏幅度较小。

    Args:
        lines: list of str, lua 文件的每行内容

    Returns: list of str, 蒸馏后的行列表
    """
    result = []
    for line in lines:
        stripped = line.strip()
        # 去除空行
        if stripped == '':
            continue
        # 去除独立注释行（-- 开头）
        if stripped.startswith('--'):
            continue
        result.append(line)
    return result


def _distill_lua_for_review(lua_content):
    """
    Lua 代码蒸馏主入口，按类型分发蒸馏，返回蒸馏结果+结构化摘要

    流程：
    1. 调用 _classify_hotfix_type 判断 hotfix 类型
    2. 按类型分发到对应蒸馏子函数
    3. 生成结构化摘要

    Args:
        lua_content: hotfix lua 文件的文本内容

    Returns: dict
        {
            'distilled': str,          # 蒸馏后的 lua 代码
            'summary': str,            # 结构化摘要，注入到 AI prompt 头部
            'original_lines': int,     # 原始行数
            'distilled_lines': int,    # 蒸馏后行数
            'type': str,               # func_mod / data_mod / other
        }
    """
    classify_result = _classify_hotfix_type(lua_content)
    hotfix_type = classify_result['type']
    lines = lua_content.strip().split('\n')
    original_lines = len(lines)

    # 按类型分发蒸馏
    if hotfix_type == _HOTFIX_TYPE_FUNC_MOD:
        distilled_lines = _distill_func_mod(lines)
    elif hotfix_type == _HOTFIX_TYPE_DATA_MOD:
        distilled_lines = _distill_data_mod(lines)
    else:
        distilled_lines = _distill_other(lines)

    distilled_content = '\n'.join(distilled_lines)
    distilled_line_count = len(distilled_lines)

    # 生成结构化摘要
    type_display = classify_result['type_display']
    summary_parts = [f"【类型】{type_display}"]

    if hotfix_type == _HOTFIX_TYPE_FUNC_MOD and classify_result['func_names']:
        func_names_str = ', '.join(classify_result['func_names'])
        summary_parts.append(f"【修改的函数】{func_names_str}")
    elif hotfix_type == _HOTFIX_TYPE_DATA_MOD:
        if classify_result['table_names']:
            summary_parts.append(f"【涉及的表】{', '.join(classify_result['table_names'])}")
        if classify_result['field_names']:
            summary_parts.append(f"【修改的字段】{', '.join(sorted(classify_result['field_names']))}")

    summary_parts.append(f"（原始 {original_lines} 行，蒸馏后 {distilled_line_count} 行）")
    summary = '\n'.join(summary_parts)

    return {
        'distilled': distilled_content,
        'summary': summary,
        'original_lines': original_lines,
        'distilled_lines': distilled_line_count,
        'type': hotfix_type,
    }


def _distill_original_func(lua_content):
    """
    原始函数体蒸馏：比 hotfix 蒸馏更保守，只去除注释和空行

    原始函数体是 AI Review 的参照基准，不能删减任何逻辑代码。

    去除规则：
    - 块注释（--[[ ... ]]）
    - 行注释（-- xxx）
    - 连续空行合并为 1 行
    - 单独的 print 调试语句

    保留规则：
    - 全部逻辑代码
    - local 变量声明（hotfix 可能依赖）
    - 条件分支、return 语句

    Args:
        lua_content: 原始函数体的文本内容

    Returns: dict, 与 _distill_lua_for_review 返回结构相同
    """
    lines = lua_content.strip().split('\n')
    original_lines = len(lines)

    # Step 1: 去除块注释（--[[ ... ]]）
    cleaned_lines = []
    in_block_comment = False
    block_comment_pattern_start = re.compile(r'^\s*--\[\[')
    block_comment_pattern_end = re.compile(r'\]\]')
    # 单行块注释：--[[ ... ]]
    single_line_block = re.compile(r'^\s*--\[\[.*\]\]\s*$')

    for line in lines:
        stripped = line.strip()

        if in_block_comment:
            # 在块注释内，寻找结束标记
            if block_comment_pattern_end.search(stripped):
                in_block_comment = False
            continue  # 跳过块注释行

        # 单行块注释
        if single_line_block.match(stripped):
            continue

        # 块注释开始
        if block_comment_pattern_start.match(stripped):
            # 可能同时包含结束标记
            if block_comment_pattern_end.search(stripped):
                continue  # 单行块注释
            in_block_comment = True
            continue

        cleaned_lines.append(line)

    # Step 2: 去除行注释、print 调试行、合并连续空行
    result = []
    prev_blank = False
    print_pattern = re.compile(r'^\s*print\s*\(')

    for line in cleaned_lines:
        stripped = line.strip()

        # 合并连续空行
        if stripped == '':
            if prev_blank:
                continue
            result.append(line)
            prev_blank = True
            continue

        prev_blank = False

        # 去除行注释（-- 开头）
        if stripped.startswith('--'):
            continue

        # 去除 print 调试语句
        if print_pattern.match(stripped):
            continue

        result.append(line)

    distilled_content = '\n'.join(result)

    # 超长函数体截断（蒸馏后超过 100 行）
    if len(result) > 100:
        # 保留函数签名 + 前 30 行 + 最后 10 行
        truncated = result[:30] + ['... (省略 {} 行) ...'.format(len(result) - 40)] + result[-10:]
        distilled_content = '\n'.join(truncated)
        result = truncated

    return {
        'distilled': distilled_content,
        'summary': '',
        'original_lines': original_lines,
        'distilled_lines': len(result),
        'type': 'original_func',
    }


# endregion


# region 项目符号索引（Phase 3 - 原始函数体上下文）

import threading as _threading

_symbol_index_is_building = False
_symbol_index_building_lock = _threading.Lock()


def _get_project_symbol_index_file_path(side, branch_type):
    """获取项目符号索引文件的本地路径（与 hotfix_func_index.json 同目录）"""
    branch_dir = _branch_dir_name(branch_type)
    if not branch_dir:
        return None
    if side == 'server':
        local_dir = os.path.join(config.P4_WORKSPACE_DIRECTORY, 'C7', 'Development', branch_dir, 'Server', 'hotfix', 'server_hotfix')
    else:
        local_dir = os.path.join(config.P4_WORKSPACE_DIRECTORY, 'C7', 'Development', branch_dir, 'Server', 'hotfix', 'client_hotfix')
    return os.path.join(local_dir, 'project_symbol_index.json')


def _get_script_p4_dir(side, branch_type):
    """获取对应 side 的项目脚本 P4 目录路径（非 Hotfix 目录）"""
    branch_dir = _branch_dir_name(branch_type)
    if not branch_dir:
        return None, None
    if side == 'server':
        p4_dir = f"//C7/Development/{branch_dir}/Server/script_lua/....lua"
        cl_path = f"//C7/Development/{branch_dir}/Server/script_lua/..."
    else:
        p4_dir = f"//C7/Development/{branch_dir}/Client/Content/Script/....lua"
        cl_path = f"//C7/Development/{branch_dir}/Client/Content/Script/..."
    return p4_dir, cl_path


def _get_latest_changelist_for_dir(p4_path):
    try:
        result = subprocess.run(
            ['p4', 'changes', '-m', '1', p4_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15
        )
        output = result.stdout.decode('utf-8', errors='replace').strip()
        if result.returncode == 0 and output:
            parts = output.split()
            if len(parts) >= 2 and parts[0] == 'Change':
                return int(parts[1])
    except Exception as e:
        app.logger.warning(f"_get_latest_changelist_for_dir failed for {p4_path}: {e}")
    return None


def _p4_run(cmd, timeout=30):
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception as e:
        app.logger.warning(f"_p4_run failed: {cmd}: {e}")
        return ""


def _normalize_filename(name):
    """
    文件名 normalize：去除下划线、转小写，用于模糊匹配
    world_utils -> worldutils, WorldBossSpace -> worldbossspace
    """
    return name.replace('_', '').replace('-', '').lower()


def _build_project_symbol_index(side, branch_type):
    """
    全量构建项目符号索引（方案 D：p4 files 建文件名 normalize 索引）

    只用 p4 files 列出所有 lua 文件路径（一次请求，几秒完成），
    构建 normalize(文件名) → [P4完整路径列表] 的映射。

    Review 时按函数名各段猜文件名，normalize 后在索引里查找候选路径，
    再 p4 print 单文件读内容定位函数体。

    并发保护：同一时间只允许一个构建任务运行。

    Args:
        side: 'server' | 'client'
        branch_type: 'weekly' | 'mainline'

    Returns: dict {'built': bool, 'skipped': bool, 'symbols_count': int, 'errMsg': str}
    """
    global _symbol_index_is_building

    # 并发锁：已有构建进行中则跳过
    if _symbol_index_is_building:
        return {'built': False, 'skipped': True, 'reason': '索引正在构建中，请稍后'}
    with _symbol_index_building_lock:
        if _symbol_index_is_building:
            return {'built': False, 'skipped': True, 'reason': '索引正在构建中，请稍后'}
        _symbol_index_is_building = True

    try:
        _, cl_path = _get_script_p4_dir(side, branch_type)
        branch_dir = _branch_dir_name(branch_type)
        if not branch_dir:
            return {'built': False, 'skipped': False, 'errMsg': f'invalid side/branch_type: {side}/{branch_type}'}

        # p4 files 路径（用 ... 递归搜索所有文件）
        if side == 'server':
            p4_files_path = f"//C7/Development/{branch_dir}/Server/script_lua/..."
        else:
            p4_files_path = f"//C7/Development/{branch_dir}/Client/Content/Script/..."

        index_file = _get_project_symbol_index_file_path(side, branch_type)
        if not index_file:
            return {'built': False, 'skipped': False, 'errMsg': 'cannot determine index file path'}

        # 获取当前 changelist
        latest_cl = _get_latest_changelist_for_dir(cl_path)

        # p4 files 列出全部文件路径（一次请求）
        try:
            result = subprocess.run(
                ['p4', 'files', p4_files_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60
            )
            result.stdout = result.stdout.decode('utf-8', errors='replace')
            result.stderr = result.stderr.decode('utf-8', errors='replace')
            files_output = result.stdout
            if result.returncode != 0 and not files_output.strip():
                err = result.stderr.strip()[:300]
                app.logger.error(f"_build_project_symbol_index: p4 files failed: {err}")
                return {'built': False, 'skipped': False, 'errMsg': f'p4 files failed: {err}'}
        except Exception as e:
            app.logger.error(f"_build_project_symbol_index: p4 files exception: {e}")
            return {'built': False, 'skipped': False, 'errMsg': f'p4 files exception: {e}'}

        # 解析 p4 files 输出，构建 normalize(basename) → [p4_path] 映射
        # 格式：//C7/.../FashionStationSystem.lua#5 - edit change 12345 (text)
        file_index = {}  # normalize_name -> [p4_full_path]
        total_files = 0

        for line in files_output.splitlines():
            line = line.strip()
            if not line.startswith('//'):
                continue
            # 跳过已删除文件
            if ' - delete ' in line:
                continue
            # 跳过 Hotfix 目录
            if '/Hotfix/' in line:
                continue
            # 提取 P4 路径（去掉 #revision 及后面的信息）
            p4_path = line.split('#')[0].strip()
            if not p4_path.endswith('.lua'):
                continue

            # 提取文件名（不含扩展名）并 normalize
            basename = p4_path.split('/')[-1]          # FashionStationSystem.lua
            name_without_ext = basename[:-4]            # FashionStationSystem
            norm_key = _normalize_filename(name_without_ext)  # fashionstationsystem

            if norm_key not in file_index:
                file_index[norm_key] = []
            file_index[norm_key].append(p4_path)
            total_files += 1

        # 写入索引文件
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        import datetime as dt
        index_data = {
            'side': side,
            'branch_type': branch_type,
            f'{side}_changelist': latest_cl,
            'file_index': file_index,   # normalize_name -> [p4_path]
            'total_files': total_files,
            'updated_at': dt.datetime.now().isoformat(),
        }
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)

        app.logger.info(f"_build_project_symbol_index: built {total_files} files for {side}/{branch_type}")
        return {'built': True, 'skipped': False, 'symbols_count': total_files}

    except Exception as e:
        app.logger.error(f"_build_project_symbol_index error: {e}")
        return {'built': False, 'skipped': False, 'errMsg': str(e)}
    finally:
        _symbol_index_is_building = False


def _load_project_symbol_index(side, branch_type):
    """
    读取项目符号索引文件，并检查 changelist 是否过期

    Returns: (file_index dict, needs_rebuild bool)
        file_index: normalize_name -> [p4_path] 映射
    """
    index_file = _get_project_symbol_index_file_path(side, branch_type)
    if not index_file or not os.path.exists(index_file):
        return None, True

    try:
        with open(index_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 兼容旧格式（symbols）和新格式（file_index）
        file_index = data.get('file_index') or data.get('symbols', {})
        cached_cl = data.get(f'{side}_changelist')

        # 检查 changelist 是否变化（只检查对应 side 的目录）
        _, cl_path = _get_script_p4_dir(side, branch_type)
        if cl_path and cached_cl:
            latest_cl = _get_latest_changelist_for_dir(cl_path)
            needs_rebuild = (latest_cl is not None and latest_cl != cached_cl)
        else:
            needs_rebuild = False

        return file_index, needs_rebuild
    except Exception as e:
        app.logger.warning(f"_load_project_symbol_index failed: {e}")
        return None, True


def _locate_func_in_file(func_name, file_content):
    """
    在 Lua 文件内容中实时定位函数体范围

    算法：
    1. 找到 func_name = function( 的起始行
    2. 从起始行开始追踪 function/end 嵌套深度
    3. 深度归零时即为函数体结束

    Args:
        func_name: 函数名，如 'FashionStationSystem.RequestNavigateTo'
        file_content: 文件完整内容字符串

    Returns: dict {'start_line': int, 'end_line': int, 'func_body': str} or None
    """
    lines = file_content.split('\n')
    # 转义函数名中的点号用于正则
    escaped = re.escape(func_name)
    # 支持两种 Lua 函数定义语法：
    # 1. 点语法：ClassName.MethodName = function(...)
    # 2. 冒号语法：function ClassName:MethodName(...)
    start_pattern = re.compile(
        r'^\s*' + escaped + r'\s*=\s*function\s*\('  # 点语法
        r'|^\s*function\s+' + escaped.replace(r'\.', r'[:.]') + r'\s*\('  # 冒号语法（: 或 . 分隔）
    )

    start_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('--'):
            continue
        if start_pattern.match(line):
            start_idx = i
            break

    if start_idx is None:
        return None

    # 追踪嵌套深度，找函数体结束的 end
    depth = 0
    end_idx = None
    func_keywords = re.compile(r'\bfunction\b')
    end_keyword = re.compile(r'\bend\b')
    # 简单字符串字面量去除（避免注释/字符串中的 function/end 影响计数）
    strip_strings = re.compile(r'"[^"]*"|\'[^\']*\'|--.*')

    for i in range(start_idx, len(lines)):
        line = lines[i]
        cleaned = strip_strings.sub('', line)
        depth += len(func_keywords.findall(cleaned))
        depth -= len(end_keyword.findall(cleaned))
        if i > start_idx and depth <= 0:
            end_idx = i
            break

    if end_idx is None:
        # 未找到结束，返回到文件末尾
        end_idx = len(lines) - 1

    func_body = '\n'.join(lines[start_idx:end_idx + 1])
    return {
        'start_line': start_idx + 1,  # 1-indexed
        'end_line': end_idx + 1,
        'func_body': func_body,
    }


def _find_original_func_body(func_name, side, branch_type):
    """
    查项目符号索引（文件名索引），多级猜文件名，p4 print 按需拉取，
    实时定位并提取原始函数体，最后蒸馏

    猜测策略（函数名 A.B.C）：
      1. C（方法名）normalize 后在 file_index 查找
      2. B（类名）normalize 后在 file_index 查找
      3. A（命名空间）normalize 后在 file_index 查找
    多级均未命中时静默降级（found=False）

    Args:
        func_name: 函数名，如 'worldBossSpace.WorldBossSpace.randomCreateWorldBossBot'
        side: 'server' | 'client'
        branch_type: 'weekly' | 'mainline'

    Returns: dict {
        'func_body': str,          # 蒸馏后的函数体
        'original_lines': int,
        'distilled_lines': int,
        'file_path': str,          # P4 文件路径
        'found': bool,
    }
    """
    not_found = {'found': False, 'func_body': '', 'file_path': '', 'original_lines': 0, 'distilled_lines': 0}

    file_index, needs_rebuild = _load_project_symbol_index(side, branch_type)

    if needs_rebuild and not _symbol_index_is_building:
        import gevent
        gevent.spawn(_build_project_symbol_index, side, branch_type)
        app.logger.info(f"_find_original_func_body: triggered async rebuild for {side}/{branch_type}")

    if not file_index:
        return not_found

    # 多级猜测候选段（函数名各段从右到左）
    parts = func_name.split('.')
    # 去掉末尾的方法名，收集所有可能的类名段
    # 例如 worldBossSpace.WorldBossSpace.randomCreateWorldBossBot
    # 候选：[randomCreateWorldBossBot, WorldBossSpace, worldBossSpace]
    candidates = list(reversed(parts))

    p4_path = None
    for candidate in candidates:
        norm = _normalize_filename(candidate)
        if norm in file_index:
            paths = file_index[norm]
            if paths:
                p4_path = paths[0]  # 取第一个匹配
                app.logger.info(f"_find_original_func_body: matched '{candidate}' -> {p4_path}")
                break

    if not p4_path:
        app.logger.info(f"_find_original_func_body: no file match for {func_name}")
        return not_found

    # p4 print 按需读取文件内容
    try:
        result = subprocess.run(
            ['p4', 'print', '-q', p4_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15
        )
        result.stdout = result.stdout.decode('utf-8', errors='replace')
        result.stderr = result.stderr.decode('utf-8', errors='replace')
        if result.returncode != 0 or not result.stdout:
            app.logger.warning(f"_find_original_func_body: p4 print failed for {p4_path}: {result.stderr[:100]}")
            return not_found
        file_content = result.stdout
    except Exception as e:
        app.logger.warning(f"_find_original_func_body: p4 print exception for {p4_path}: {e}")
        return not_found

    # 实时定位函数体
    loc = _locate_func_in_file(func_name, file_content)
    if not loc:
        # 部分函数名可能用短名（不含命名空间前缀），尝试最后两段
        short_name = '.'.join(parts[-2:]) if len(parts) >= 2 else func_name
        if short_name != func_name:
            loc = _locate_func_in_file(short_name, file_content)
    if not loc:
        app.logger.warning(f"_find_original_func_body: func {func_name} not located in {p4_path}")
        return {'found': False, 'func_body': '', 'file_path': p4_path, 'original_lines': 0, 'distilled_lines': 0}

    # 蒸馏原始函数体
    distill_result = _distill_original_func(loc['func_body'])

    return {
        'found': True,
        'func_body': distill_result['distilled'],
        'original_lines': distill_result['original_lines'],
        'distilled_lines': distill_result['distilled_lines'],
        'file_path': p4_path,
    }

# endregion


def _get_func_index_file_path(side, branch_type):
    """获取函数名索引文件的本地路径"""
    branch_dir = _branch_dir_name(branch_type)
    if not branch_dir:
        return None
    if side == 'server':
        local_dir = os.path.join(config.P4_WORKSPACE_DIRECTORY, 'C7', 'Development', branch_dir, 'Server', 'hotfix', 'server_hotfix')
    else:
        local_dir = os.path.join(config.P4_WORKSPACE_DIRECTORY, 'C7', 'Development', branch_dir, 'Server', 'hotfix', 'client_hotfix')
    return os.path.join(local_dir, 'hotfix_func_index.json')


def _build_hotfix_func_index(side, branch_type, notify=True, force=False):
    """
    全量扫描 hotfix 目录，构建「文件→函数名」索引并存储到 DB

    Args:
        side: 'server' | 'client'
        branch_type: 'weekly' | 'mainline'
        notify: 构建完成后是否自动做全量冲突检测+Kim 通知（默认 True）
        force: 为 True 时跳过缓存检查，强制重新扫描

    Returns: dict 索引数据 {filename: [func_name_list]}，或 None（跳过）
    """
    branch_dir = _branch_dir_name(branch_type)
    if not branch_dir:
        return None

    if not force:
        cached = _get_cached_index(side, branch_type)
        if cached:
            app.logger.info(f"_build_hotfix_func_index: cache hit for {side}/{branch_type}, skip build")
            return None

    try:

        # 构建 P4 目录路径
        if side == 'server':
            p4_dir = f"//C7/Development/{branch_dir}/Server/hotfix/server_hotfix/"
            local_dir = os.path.join(config.P4_WORKSPACE_DIRECTORY, 'C7', 'Development', branch_dir, 'Server', 'hotfix', 'server_hotfix')
        else:
            p4_dir = f"//C7/Development/{branch_dir}/Server/hotfix/client_hotfix/"
            local_dir = os.path.join(config.P4_WORKSPACE_DIRECTORY, 'C7', 'Development', branch_dir, 'Server', 'hotfix', 'client_hotfix')

        current_changelist = _get_latest_changelist_for_dir(p4_dir.rstrip('/') + '/...')

        # 同步 P4 目录下的所有 lua 文件到本地
        try:
            p4Utils.update_dir(p4_dir, config.P4_WORKSPACE_DIRECTORY, force=True)
        except Exception as e:
            app.logger.error(f"_build_hotfix_func_index: update P4 dir failed: {e}")
            return {}

        # 删除本地多余的文件（P4 上已删除但本地仍存在的）
        try:
            p4_files_output = _p4_run(["p4", "files", "-e", f"{p4_dir.rstrip('/')}/..."])
            p4_valid_names = set()
            if p4_files_output:
                for line in p4_files_output.splitlines():
                    s = (line or "").strip()
                    if not s.startswith("//") or " delete " in s.lower():
                        continue
                    depot_file = s.split("#", 1)[0].strip()
                    p4_valid_names.add(os.path.basename(depot_file))
            if p4_valid_names and os.path.exists(local_dir):
                for fname in os.listdir(local_dir):
                    if fname.endswith('.lua') and fname.startswith('hotfix_') and fname not in p4_valid_names:
                        stale_path = os.path.join(local_dir, fname)
                        os.remove(stale_path)
                        app.logger.info(f"_build_hotfix_func_index: removed stale local file {fname}")
        except Exception as e:
            app.logger.warning(f"_build_hotfix_func_index: clean stale files failed: {e}")

        # 遍历所有 .lua 文件
        index = {}
        if not os.path.exists(local_dir):
            app.logger.warning(f"_build_hotfix_func_index: local dir not found: {local_dir}")
            return {}

        for fname in os.listdir(local_dir):
            if not fname.endswith('.lua'):
                continue
            # 跳过 manifest 或非 hotfix 文件
            if fname == 'manifest.lua' or not fname.startswith('hotfix_'):
                continue
            file_path = os.path.join(local_dir, fname)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lua_content = f.read()
                func_names = _extract_func_names_from_lua(lua_content)
                index[fname] = func_names
            except Exception as e:
                app.logger.warning(f"_build_hotfix_func_index: failed to read {fname}: {e}")
                index[fname] = []

        # 存储到本地 JSON 文件
        index_file_path = _get_func_index_file_path(side, branch_type)
        if index_file_path:
            os.makedirs(os.path.dirname(index_file_path), exist_ok=True)
            with open(index_file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'side': side,
                    'branch_type': branch_type,
                    'index': index,
                    'changelist': current_changelist,
                    'updated_at': datetime.now().isoformat(),
                }, f, ensure_ascii=False, indent=2)

        app.logger.info(f"_build_hotfix_func_index: built index for {side}/{branch_type}, {len(index)} files, {sum(len(v) for v in index.values())} func refs")

        # 写入内存缓存
        if index:
            _set_cached_index(side, branch_type, index)
            app.logger.info(f"_build_hotfix_func_index: cached index written for {side}/{branch_type}, cache_key='{side}/{branch_type}'")
        else:
            app.logger.warning(f"_build_hotfix_func_index: index is empty for {side}/{branch_type}, skip cache write")

        # 构建完成后自动做全量冲突检测+Kim 通知
        if notify and index:
            try:
                _detect_and_notify_conflicts(
                    list(index.keys()), side, branch_type,
                    trigger_source='manifest',
                )
            except Exception as _cn_err:
                app.logger.warning(f"_build_hotfix_func_index: post-build conflict notify failed: {_cn_err}")

        return index

    except Exception as e:
        app.logger.error(f"_build_hotfix_func_index: error for {side}/{branch_type}: {e}")
        return None


def _incremental_build_hotfix_func_index(side, branch_type, notify=True):
    """
    增量构建索引：只同步和解析自上次构建以来变更的文件，合并到已有索引

    Args:
        side: 'server' | 'client'
        branch_type: 'weekly' | 'mainline'
        notify: 是否触发冲突检测+通知

    Returns: dict {files: int, funcs: int, changed: int, message: str}
    """
    branch_dir = _branch_dir_name(branch_type)
    if not branch_dir:
        return {'files': 0, 'funcs': 0, 'changed': 0, 'message': 'invalid side/branch_type'}

    try:
        if side == 'server':
            p4_dir = f"//C7/Development/{branch_dir}/Server/hotfix/server_hotfix/"
            local_dir = os.path.join(config.P4_WORKSPACE_DIRECTORY, 'C7', 'Development', branch_dir, 'Server', 'hotfix', 'server_hotfix')
        else:
            p4_dir = f"//C7/Development/{branch_dir}/Server/hotfix/client_hotfix/"
            local_dir = os.path.join(config.P4_WORKSPACE_DIRECTORY, 'C7', 'Development', branch_dir, 'Server', 'hotfix', 'client_hotfix')

        current_cl = _get_latest_changelist_for_dir(p4_dir.rstrip('/') + '/...')

        index_file_path = _get_func_index_file_path(side, branch_type)
        old_index = {}
        old_changelist = None
        if index_file_path and os.path.exists(index_file_path):
            try:
                with open(index_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                old_index = data.get('index', {})
                old_changelist = data.get('changelist')
            except Exception as e:
                app.logger.warning(f"_incremental_build_hotfix_func_index: load old index failed: {e}")

        if not old_index:
            app.logger.info(f"_incremental_build_hotfix_func_index: no existing index for {side}/{branch_type}, fallback to full build")
            full_index = _build_hotfix_func_index(side, branch_type, notify=notify, force=True)
            if full_index is None:
                return {'files': 0, 'funcs': 0, 'changed': 0, 'message': '索引无变化'}
            if not full_index:
                return {'files': 0, 'funcs': 0, 'changed': 0, 'message': '全量构建失败'}
            func_count = sum(len(v) for v in full_index.values())
            return {'files': len(full_index), 'funcs': func_count, 'changed': 0, 'message': '无已有索引，已执行全量构建'}

        if current_cl is not None and old_changelist is not None and current_cl <= old_changelist:
            func_count = sum(len(v) for v in old_index.values())
            app.logger.info(f"_incremental_build_hotfix_func_index: {side}/{branch_type} no changes (cl={current_cl} <= old={old_changelist})")
            return {'files': len(old_index), 'funcs': func_count, 'changed': 0, 'message': f'索引无变化 (cl={current_cl})'}

        changed_files = set()
        deleted_files = set()

        if current_cl is not None and old_changelist is not None:
            try:
                from utility.p4Utils import _run_p4
                output = _run_p4(['p4', 'changes', f"{p4_dir.rstrip('/')}/...@{old_changelist + 1},#head"])
            except Exception:
                output = ""

            cl_list = []
            if output:
                for line in output.splitlines():
                    s = (line or "").strip()
                    if s.startswith('Change '):
                        parts = s.split()
                        if len(parts) >= 2:
                            try:
                                cl_list.append(int(parts[1]))
                            except ValueError:
                                pass

            for cl_num in cl_list:
                try:
                    desc_output = _run_p4(['p4', 'describe', '-s', str(cl_num)])
                    if not desc_output:
                        continue
                    for line in desc_output.splitlines():
                        s = (line or "").strip()
                        if not s.startswith('... '):
                            continue
                        file_part = s[4:]
                        depot_file = file_part.split('#', 1)[0].strip()
                        fname = os.path.basename(depot_file)
                        if not fname.endswith('.lua') or not fname.startswith('hotfix_') or fname == 'manifest.lua':
                            continue
                        if 'delete' in line.lower():
                            deleted_files.add(fname)
                        else:
                            changed_files.add(fname)
                except Exception as e:
                    app.logger.warning(f"_incremental_build_hotfix_func_index: describe cl {cl_num} failed: {e}")
        else:
            try:
                p4_files_output = _run_p4(["p4", "files", "-e", f"{p4_dir.rstrip('/')}/..."])
                if p4_files_output:
                    for line in p4_files_output.splitlines():
                        s = (line or "").strip()
                        if not s.startswith("//") or " delete " in s.lower():
                            if s.startswith("//"):
                                deleted_files.add(os.path.basename(s.split("#", 1)[0].strip()))
                            continue
                        depot_file = s.split("#", 1)[0].strip()
                        fname = os.path.basename(depot_file)
                        if fname.endswith('.lua') and fname.startswith('hotfix_') and fname != 'manifest.lua':
                            changed_files.add(fname)
            except Exception as e:
                app.logger.warning(f"_incremental_build_hotfix_func_index: p4 files failed: {e}")

        changed_files -= deleted_files
        conflict_summary = {}

        if not changed_files and not deleted_files:
            func_count = sum(len(v) for v in old_index.values())
            new_index = old_index
            app.logger.info(f"_incremental_build_hotfix_func_index: {side}/{branch_type} no changed files (cl={current_cl})")
            if current_cl is not None and index_file_path:
                os.makedirs(os.path.dirname(index_file_path), exist_ok=True)
                with open(index_file_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'side': side,
                        'branch_type': branch_type,
                        'index': new_index,
                        'changelist': current_cl,
                        'updated_at': datetime.now().isoformat(),
                    }, f, ensure_ascii=False, indent=2)
                _invalidate_cached_index(side, branch_type)
                _set_cached_index(side, branch_type, new_index)
        else:
            for fname in changed_files:
                try:
                    p4Utils.download_file(
                        f"{p4_dir}{fname}",
                        os.path.join(local_dir, fname)
                    )
                except Exception as e:
                    app.logger.warning(f"_incremental_build_hotfix_func_index: sync {fname} failed: {e}")

            for fname in deleted_files:
                stale_path = os.path.join(local_dir, fname)
                if os.path.exists(stale_path):
                    os.remove(stale_path)
                    app.logger.info(f"_incremental_build_hotfix_func_index: removed deleted file {fname}")

            new_index = dict(old_index)

            for fname in deleted_files:
                new_index.pop(fname, None)

            for fname in changed_files:
                file_path = os.path.join(local_dir, fname)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lua_content = f.read()
                    new_index[fname] = _extract_func_names_from_lua(lua_content)
                except Exception as e:
                    app.logger.warning(f"_incremental_build_hotfix_func_index: parse {fname} failed: {e}")
                    new_index[fname] = []

            func_count = sum(len(v) for v in new_index.values())

            if index_file_path:
                os.makedirs(os.path.dirname(index_file_path), exist_ok=True)
                with open(index_file_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'side': side,
                        'branch_type': branch_type,
                        'index': new_index,
                        'changelist': current_cl,
                        'updated_at': datetime.now().isoformat(),
                    }, f, ensure_ascii=False, indent=2)

            _invalidate_cached_index(side, branch_type)
            _set_cached_index(side, branch_type, new_index)

            app.logger.info(
                f"_incremental_build_hotfix_func_index: {side}/{branch_type} done, "
                f"changed={len(changed_files)}, deleted={len(deleted_files)}, "
                f"total_files={len(new_index)}, func_refs={func_count}"
            )

            if notify and new_index:
                try:
                    conflict_summary = _detect_and_notify_conflicts(
                        list(changed_files), side, branch_type,
                        trigger_source='manifest',
                    )
                except Exception as _cn_err:
                    conflict_summary = {}
                    app.logger.warning(f"_incremental_build_hotfix_func_index: conflict notify failed: {_cn_err}")

        return {
            'files': len(new_index),
            'funcs': func_count,
            'changed': len(changed_files),
            'deleted': len(deleted_files),
            'conflicts_detected': conflict_summary.get('detected', 0) if notify else 0,
            'conflicts_notified_authors': conflict_summary.get('notified_authors', []) if notify else [],
            'message': f'增量构建完成，更新{len(changed_files)}个文件，删除{len(deleted_files)}个文件' if changed_files or deleted_files else f'CL已更新但无hotfix文件变化 (cl={old_changelist}->{current_cl})'
        }

    except Exception as e:
        app.logger.error(f"_incremental_build_hotfix_func_index: error for {side}/{branch_type}: {e}")
        return {'files': 0, 'funcs': 0, 'changed': 0, 'message': str(e)}


def _update_hotfix_func_index(file_name, lua_content, side, branch_type):
    """
    增量更新：解析单个新文件并追加到索引（本地 JSON 文件）

    Args:
        file_name: hotfix 文件名（如 'hotfix_zhangyu73_282350.lua'）
        lua_content: 文件内容
        side: 'server' | 'client'
        branch_type: 'weekly' | 'mainline'

    Returns: list of func_names for this file
    """
    func_names = _extract_func_names_from_lua(lua_content)

    # 加载现有索引并更新
    index_file_path = _get_func_index_file_path(side, branch_type)
    if index_file_path and os.path.exists(index_file_path):
        with open(index_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data['index'][file_name] = func_names
        data['updated_at'] = datetime.now().isoformat()
        with open(index_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # 增量更新后失效内存缓存，下次请求重新加载
        _invalidate_cached_index(side, branch_type)
    else:
        _start_build_index(side, branch_type, force_full=True)

    app.logger.info(f"_update_hotfix_func_index: updated {file_name} for {side}/{branch_type}, func_names={func_names}")
    return func_names


def _find_related_hotfix_files(file_name, side, branch_type, full_index=None):
    """
    根据当前文件修改的函数名，查找所有修改相同函数的其他文件

    Args:
        file_name: 当前 hotfix 文件名
        side: 'server' | 'client'
        branch_type: 'weekly' | 'mainline'
        full_index: 可选，已加载的索引 dict，不传则从 JSON 文件读取

    Returns: list of dict, 每项包含:
        - file_name: 关联文件名
        - func_names: 该文件修改的函数名列表（与当前文件重叠的部分）
    """
    if full_index is None:
        index_file_path = _get_func_index_file_path(side, branch_type)
        if index_file_path and os.path.exists(index_file_path):
            with open(index_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            full_index = data.get('index', {})

    if not full_index:
        return None

    # 获取当前文件的函数名
    current_func_names = full_index.get(file_name, [])
    if not current_func_names:
        return []

    # 查找修改相同函数的其他文件
    related = []
    current_set = set(current_func_names)
    for other_file, other_funcs in full_index.items():
        if other_file == file_name:
            continue
        overlap = set(other_funcs) & current_set
        if overlap:
            related.append({
                'file_name': other_file,
                'func_names': list(overlap),
            })

    return related


# endregion

# region route
def _normalize_branch_type(branchType):
    if branchType is None:
        return 'weekly'
    v = str(branchType).strip().lower()
    if v in ('mainline', 'main'):
        return 'mainline'
    if v in ('weekly', 'week'):
        return 'weekly'
    return v


def _normalize_hotfix_env(env_value):
    v = str(env_value or '').strip().lower()
    if v in ('test', 'dev', 'develop', 'development', 'qa', '测试'):
        return 'test'
    if v in ('prod', 'production', 'release', 'formal', '正式'):
        return 'prod'
    return 'prod'


def _branch_dir_name(branchType):
    normalized = _normalize_branch_type(branchType)
    if normalized == 'weekly':
        return 'Weekly'
    if normalized == 'mainline':
        return 'Mainline'
    return None


def _parse_bool(value, default=True):
    if value is None:
        return default
    v = str(value).strip().lower()
    if v in ('1', 'true', 'yes', 'y', 'on'):
        return True
    if v in ('0', 'false', 'no', 'n', 'off'):
        return False
    return default


def _get_hotfix_lua_local_path(file_name, side, branch_type):
    """获取 hotfix lua 文件的本地路径（用于增量更新索引时读取文件内容）"""
    branch_dir = _branch_dir_name(branch_type)
    if not branch_dir:
        return None
    if side == 'server':
        return os.path.join(config.P4_WORKSPACE_DIRECTORY, 'C7', 'Development', branch_dir, 'Server', 'hotfix', 'server_hotfix', file_name)
    else:
        return os.path.join(config.P4_WORKSPACE_DIRECTORY, 'C7', 'Development', branch_dir, 'Server', 'hotfix', 'client_hotfix', file_name)

def _get_hotfix_manifest_paths(hotfixType, branchType, env_value=None):
    env_value = _normalize_hotfix_env(env_value)
    manifest_name = 'manifest_ci_use__.json' if env_value == 'test' else 'manifest.json'

    if hotfixType not in ('server', 'client', 'crates'):
        return None, None, jsonify({'errMsg': f'Invalid hotfixType: {hotfixType}'}), 400

    branchDir = 'Weekly'
    hotfixManifestP4File = f"//C7/Development/{branchDir}/Server/hotfix/{hotfixType}_hotfix/{manifest_name}"
    hotfixManifestLocalFile = os.path.join(config.P4_MINI_WORKSPACE_DIRECTORY, hotfixManifestP4File.replace("//", ""))
    return hotfixManifestP4File, hotfixManifestLocalFile, None, None


def _run_p4_cmd(args, input_text=None):
    p4_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'p4'))
    proc = subprocess.run(
        args,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=p4_dir,
        check=False,
    )
    return proc.returncode, (proc.stdout or '').strip(), (proc.stderr or '').strip()


def _create_changelist(description, workspace):
    code, out, err = _run_p4_cmd(['p4', '-c', workspace, 'change', '-o'])
    if code != 0 or not out:
        return None, err or out or 'p4 change -o failed'

    desc_lines = [l for l in str(description).splitlines() if l is not None]
    if not desc_lines:
        desc_lines = ['[ManifestAutoCommit] Manifest']

    new_spec_lines = []
    lines = out.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('Description:'):
            new_spec_lines.append('Description:')
            for dl in desc_lines:
                new_spec_lines.append('\t' + dl)
            i += 1
            while i < len(lines) and lines[i].startswith('\t'):
                i += 1
            continue
        new_spec_lines.append(line)
        i += 1

    spec_text = '\n'.join(new_spec_lines) + '\n'
    code, out, err = _run_p4_cmd(['p4', '-c', workspace, 'change', '-i'], input_text=spec_text)
    if code != 0:
        return None, err or out or 'p4 change -i failed'

    m = re.search(r'Change\s+(\d+)\s+created', out)
    if not m:
        m = re.search(r'Change\s+(\d+)\s+created', err)
    if not m:
        m = re.search(r'Change\s+(\d+)', out) or re.search(r'Change\s+(\d+)', err)
    if not m:
        return None, out or err or 'create changelist failed'

    return int(m.group(1)), None


def _cleanup_workspace_pending(workspace):
    ws = workspace if workspace is not None else ''
    if not ws:
        return False, 'Missing workspace'

    code, out, err = _run_p4_cmd(['p4', '-c', ws, 'revert', '//...'])
    if code != 0:
        return False, err or out or 'p4 revert failed'

    code, out, err = _run_p4_cmd(['p4', '-c', ws, 'changes', '-s', 'pending', '-c', ws])
    if code != 0:
        return False, err or out or 'p4 changes failed'

    change_ids = []
    for line in (out or '').splitlines():
        m = re.match(r'^Change\s+(\d+)\b', line.strip())
        if not m:
            continue
        cid = int(m.group(1))
        if cid > 0:
            change_ids.append(cid)

    for cid in change_ids:
        code, out, err = _run_p4_cmd(['p4', '-c', ws, 'change', '-d', str(cid)])
        if code == 0:
            continue

        _run_p4_cmd(['p4', '-c', ws, 'revert', '-c', str(cid), '//...'])
        code2, out2, err2 = _run_p4_cmd(['p4', '-c', ws, 'change', '-d', str(cid)])
        if code2 != 0:
            return False, err2 or out2 or err or out or f'p4 change -d failed: {cid}'

    return True, None

@app.route('/uploadLuaFile', methods=['POST'])
def uploadLuaFile():
    """上传Lua文件到服务器并返回文件路径"""
    app.logger.info("czx uploadLuaFile")
    
    try:
        data = request.get_json()
        file_content = data.get('fileContent')
        file_name = data.get('fileName')
        
        if not file_content:
            return jsonify({
                'code': -1,
                'errMsg': '文件内容不能为空',
                'filePath': ''
            })
            
        if not file_name:
            return jsonify({
                'code': -1,
                'errMsg': '文件名不能为空',
                'filePath': ''
            })
            
        # 检查文件扩展名
        if not file_name.endswith('.lua'):
            return jsonify({
                'code': -1,
                'errMsg': '只支持.lua文件',
                'filePath': ''
            })
        
        # 创建上传目录
        upload_dir = os.path.join(os.path.dirname(__file__), '..', 'uploads')
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        
        # 生成唯一文件名：原文件名_时间戳_uuid
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        base_name = os.path.splitext(file_name)[0]
        new_file_name = f"{base_name}_{timestamp}_{unique_id}.lua"
        
        # 保存文件
        file_path = os.path.join(upload_dir, new_file_name)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        # 返回相对路径，用于后续读取
        relative_path = f"uploads/{new_file_name}"
        
        app.logger.info(f"文件上传成功: {relative_path}")
        
        return jsonify({
            'code': 0,
            'errMsg': '',
            'filePath': relative_path,
            'originalFileName': file_name
        })
        
    except Exception as e:
        app.logger.error(f"文件上传失败: {str(e)}")
        return jsonify({
            'code': -1,
            'errMsg': f'文件上传失败: {str(e)}',
            'filePath': ''
        })

@app.route('/getC7Server', methods=['GET'])
def getC7Server():
    app.logger.info("getC7Server")
    
    # 尝试从缓存读取
    cached_data = _get_cached_c7_data('c7_server')
    if cached_data is not None:
        app.logger.debug("getC7Server: 使用缓存数据")
        return jsonify({'data': cached_data})
    
    # 构建文件路径
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'C7')
    c7_server_path = os.path.join(data_dir, 'c7Server.json')
    
    with open(c7_server_path, 'r', encoding='utf-8') as f:
        c7_server_data = json.load(f)
        # 缓存数据
        _set_cached_c7_data('c7_server', c7_server_data)
        result = {
            'data': c7_server_data,
        }
        
        return jsonify(result)

@app.route('/getC7ServerTags', methods=['GET'])
def getC7ServerTags():
    app.logger.info("getC7ServerTags")
    
    # 尝试从缓存读取
    cached_data = _get_cached_c7_data('c7_tags')
    if cached_data is not None:
        app.logger.debug("getC7ServerTags: 使用缓存数据")
        return jsonify({'data': cached_data})

    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'C7')
    tags_path = os.path.join(data_dir, 'c7ServerTags.json')
    try:
        with open(tags_path, 'r', encoding='utf-8') as f:
            data = json.load(f) or {}
        # 缓存数据
        _set_cached_c7_data('c7_tags', data)
        return jsonify({'data': data})
    except FileNotFoundError:
        return jsonify({'data': {}})
    except Exception as e:
        app.logger.error(f"getC7ServerTags failed: {e}")
        return jsonify({'errMsg': str(e)}), 500
    
@app.route('/getC7Hotfix', methods=['GET'])
def getC7Hotfix():
    app.logger.info("getC7Hotfix")
    hotfixType = request.args.get('hotfixType')
    branchType = request.args.get('branchType') or 'weekly'
    branchDir = 'Weekly'
    
    if hotfixType not in ('server', 'client', 'crates'):
        return jsonify({'errMsg': f'Invalid hotfixType: {hotfixType}'}), 400
    
    p4HotfixDir = f"//C7/Development/{branchDir}/Server/hotfix/{hotfixType}_hotfix"
    cache_key = f"hotfix_{hotfixType}_{branchType}"
    
    # 先快速查询 P4 获取文件列表（list_dir 很快，主要是 metadata）
    hotfixList = p4Utils.list_dir(p4HotfixDir)
    
    # 计算最大 changelist
    max_changelist = 0
    for f in hotfixList:
        current_cl = int(f.get('changelist') or 0)
        max_changelist = max(max_changelist, current_cl)
    
    # 检查缓存：如果 changelist 未变，直接返回缓存数据
    cached_entry = _get_cached_p4_data(cache_key, skip_cl_check=True)
    if cached_entry and cached_entry.get('changelist') == max_changelist and max_changelist > 0:
        app.logger.debug(f"P4 cache hit: {cache_key} @ CL {max_changelist}")
        return jsonify(cached_entry['data'])
    
    # changelist 变化或无缓存，需要过滤和处理数据
    app.logger.debug(f"P4 cache miss: {cache_key} (processing file list)")
    filtered_list = []
    for f in hotfixList:
        fname = os.path.basename(f.get('name') or '')
        if not fname:
            continue
        lower = fname.lower()
        if lower in ('manifest.json', 'manifest_ci_use__.json'):
            continue
        base_name = os.path.splitext(fname)[0]
        if base_name.lower() in ('manifest', 'manifest_ci_use__'):
            continue
        
        # 对服务端类型，只返回.lua文件
        if hotfixType in ['server', 'client']:
            if not fname.lower().endswith('.lua'):
                continue
        
        f['name'] = base_name
        filtered_list.append(f)
            
    # 将列表转换为字典，key为文件名，value为文件信息
    result_dict = {}
    for f in filtered_list:
        key = f['name']
        current_cl = int(f.get('changelist') or 0)
        
        if key in result_dict:
            if current_cl >= int(result_dict[key].get('changelist') or 0):
                result_dict[key] = f
        else:
            result_dict[key] = f
    
    result = {
        'hotfixType': hotfixType,
        'branchType': 'weekly',
        'data': result_dict,
    }
    
    # 更新缓存
    _set_cached_p4_data(cache_key, p4HotfixDir, result, max_changelist)
    
    return jsonify(result)

@app.route('/getHotfixManifest', methods=['GET'])
def getHotfixManifest():
    app.logger.info("getHotfixManifest")
    
    hotfixType = request.args.get('hotfixType')
    branchType = request.args.get('branchType') or 'weekly'
    env_value = _normalize_hotfix_env(request.args.get('env'))
    syncP4 = _parse_bool(request.args.get('syncP4'), default=True)

    if hotfixType not in ('server', 'client', 'crates'):
        return jsonify({'errMsg': f'Invalid hotfixType: {hotfixType}'}), 400

    manifest_name = 'manifest_ci_use__.json' if env_value == 'test' else 'manifest.json'
    hotfixManifestP4File = f"//C7/Development/Weekly/Server/hotfix/{hotfixType}_hotfix/{manifest_name}"
    hotfixManifestLocalFile = os.path.join(config.P4_WORKSPACE_DIRECTORY, hotfixManifestP4File.replace("//", ""))
    
    # 缓存key必须包含manifest_name，避免test和prod环境的缓存互相覆盖
    cache_key = f"manifest_{hotfixType}_{branchType}_{env_value}_{manifest_name}"
    
    # 如果不强制同步，尝试从缓存读取（会自动校验 changelist）
    if not syncP4:
        cached_result = _get_cached_p4_data(cache_key, hotfixManifestP4File)
        if cached_result is not None:
            return jsonify(cached_result)
    
    # 需要同步或缓存失效，从 P4 更新文件
    if syncP4:
        ret = p4Utils.update_file(hotfixManifestP4File, hotfixManifestLocalFile, force=True, changelist=0)
        if not ret:
            app.logger.error(f"update hotfix manifest file failed: {hotfixManifestP4File}")
            return jsonify({'errMsg': f'update hotfix manifest file failed: {hotfixManifestP4File}'}), 400
    else:
        if not os.path.exists(hotfixManifestLocalFile):
            return jsonify({'errMsg': f'local hotfix manifest file not found: {hotfixManifestLocalFile}'}), 404

    # 获取最新 changelist
    manifest_p4_path_at_cl = ""
    manifest_changelist = 0
    try:
        manifest_changelist = int(p4Utils.get_latest_changelist(hotfixManifestP4File) or 0)
        if manifest_changelist > 0:
            manifest_p4_path_at_cl = f"{hotfixManifestP4File.split('#')[0].split('@')[0]}@{manifest_changelist}"
    except Exception as e:
        app.logger.error(f"getHotfixManifest: get_latest_changelist failed: {e}")

    # 读取文件内容
    with open(hotfixManifestLocalFile, 'r', encoding='utf-8') as f:
        hotfix_manifest_data = json.load(f)
    
    # 组合返回结果
    result = {
        'hotfixType': hotfixType,
        'branchType': 'weekly',
        'env': env_value,
        'manifestP4Path': hotfixManifestP4File,
        'manifestP4PathAtCL': manifest_p4_path_at_cl,
        'manifestChangelist': manifest_changelist,
        'data': hotfix_manifest_data,
    }
    
    # 缓存结果
    _set_cached_p4_data(cache_key, hotfixManifestP4File, result, manifest_changelist)
    
    return jsonify(result)

@app.route('/getHotfixManifestHistory', methods=['GET'])
def getHotfixManifestHistory():
    """获取Hotfix Manifest的P4提交历史(支持分页和diff)
    
    参数:
        hotfixType: server/client/crates
        branchType: weekly/mainline (默认weekly)
        env: prod/test (默认prod)
        offset: 偏移量 (默认0)
        limit: 每页数量 (默认10)
    
    返回:
        {
            "total": 100,  // 总记录数
            "history": [
                {
                    "changelist": 12345,
                    "revision": 10,
                    "time": "2025/01/01 12:00:00",
                    "submitter": "username",
                    "description": "commit message",
                    "content": "[...]",  // manifest.json内容
                    "diffOperations": [  // 与上一版本的diff
                        {"type": "add", "fileName": "hotfix_001.lua"},
                        {"type": "remove", "fileName": "hotfix_002.lua"},
                        {"type": "modify", "fileName": "hotfix_003.lua"}
                    ]
                },
                ...
            ]
        }
    """
    app.logger.info("getHotfixManifestHistory")
    
    hotfixType = request.args.get('hotfixType')
    branchType = request.args.get('branchType') or 'weekly'
    env_value = _normalize_hotfix_env(request.args.get('env'))
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 10))
    
    if hotfixType not in ('server', 'client', 'crates'):
        return jsonify({'errMsg': f'Invalid hotfixType: {hotfixType}'}), 400
    
    manifest_name = 'manifest_ci_use__.json' if env_value == 'test' else 'manifest.json'
    hotfixManifestP4File = f"//C7/Development/Weekly/Server/hotfix/{hotfixType}_hotfix/{manifest_name}"
    
    # 构建缓存目录 - 为test和prod环境使用不同的缓存目录
    cache_dir_suffix = '_test' if env_value == 'test' else ''
    history_cache_dir = os.path.join(config.P4_WORKSPACE_DIRECTORY, 'C7', 'Development', 'Weekly', 'Server', 'hotfix', f'{hotfixType}_hotfix', f'.history_cache{cache_dir_suffix}')
    diff_cache_dir = os.path.join(history_cache_dir, 'diffs')
    os.makedirs(history_cache_dir, exist_ok=True)
    os.makedirs(diff_cache_dir, exist_ok=True)
    
    # 全量缓存key(缓存所有历史记录) - 必须包含manifest_name，避免test和prod环境的缓存互相覆盖
    full_cache_key = f"manifest_history_full_{hotfixType}_{branchType}_{env_value}_{manifest_name}"
    
    # 尝试从缓存读取全量历史
    cached_entry = _get_cached_p4_data(full_cache_key, skip_cl_check=True)
    all_history_list = None
    
    if cached_entry:
        latest_cl = int(p4Utils.get_latest_changelist(hotfixManifestP4File) or 0)
        if latest_cl > 0 and latest_cl == cached_entry.get('latest_cl', 0):
            app.logger.info(f"Manifest history cache hit: {full_cache_key}")
            all_history_list = cached_entry['data'].get('all_history', [])
    
    # 如果没有缓存或缓存失效，重新获取
    if not all_history_list:
        try:
            # 获取P4文件所有历史(最多200条)
            history_list = p4Utils.get_file_history(hotfixManifestP4File, 200)
            
            if not history_list:
                return jsonify({'total': 0, 'history': []})
            
            all_history_list = []
            
            for idx, record in enumerate(history_list):
                changelist = record['changelist']
                revision = record['revision']
                
                # 构建历史版本文件路径
                history_file_path = os.path.join(history_cache_dir, f"{manifest_name}#{revision}")
                
                # 如果缓存文件不存在，下载该版本
                if not os.path.exists(history_file_path):
                    p4_file_at_revision = f"{hotfixManifestP4File}#{revision}"
                    try:
                        p4Utils.download_file(p4_file_at_revision, history_file_path)
                    except Exception as e:
                        app.logger.error(f"Failed to download {p4_file_at_revision}: {e}")
                        continue
                
                # 读取文件内容
                try:
                    with open(history_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        manifest_data = json.loads(content)
                except Exception as e:
                    app.logger.error(f"Failed to read/parse {history_file_path}: {e}")
                    continue
                
                # 计算与上一版本的diff
                diff_operations = []
                if idx < len(history_list) - 1:
                    # 有上一个版本
                    prev_record = history_list[idx + 1]
                    prev_revision = prev_record['revision']
                    
                    # 构建diff缓存文件路径
                    diff_cache_file = os.path.join(diff_cache_dir, f"manifest_diff_{prev_revision}to{revision}.json")
                    
                    # 尝试从缓存读取diff并验证格式
                    if os.path.exists(diff_cache_file):
                        try:
                            with open(diff_cache_file, 'r', encoding='utf-8') as df:
                                cached_diff = json.load(df)
                                # 验证格式：必须是数组，且每个元素有type和diffInfo字段
                                if isinstance(cached_diff, list):
                                    is_valid = True
                                    for item in cached_diff:
                                        if not isinstance(item, dict) or 'type' not in item or 'diffInfo' not in item:
                                            is_valid = False
                                            break
                                    if is_valid:
                                        diff_operations = cached_diff
                                    else:
                                        app.logger.info(f"Invalid diff cache format, will recalculate: {diff_cache_file}")
                        except Exception as e:
                            app.logger.warning(f"Failed to read diff cache: {e}")
                    
                    # 如果没有有效缓存，计算diff
                    if not diff_operations:
                        prev_file_path = os.path.join(history_cache_dir, f"{manifest_name}#{prev_revision}")
                        
                        # 确保前一版本文件存在
                        if not os.path.exists(prev_file_path):
                            p4_file_at_prev = f"{hotfixManifestP4File}#{prev_revision}"
                            try:
                                p4Utils.download_file(p4_file_at_prev, prev_file_path)
                            except Exception as e:
                                app.logger.warning(f"Failed to download previous version {p4_file_at_prev}: {e}")
                        
                        # 计算diff
                        if os.path.exists(prev_file_path):
                            try:
                                with open(prev_file_path, 'r', encoding='utf-8') as pf:
                                    prev_content = pf.read()
                                    prev_data = json.loads(prev_content)
                                
                                # 计算操作差异
                                diff_operations = _calculate_manifest_diff(prev_data, manifest_data)
                                
                                # 缓存diff结果
                                try:
                                    with open(diff_cache_file, 'w', encoding='utf-8') as df:
                                        json.dump(diff_operations, df, ensure_ascii=False, indent=2)
                                    app.logger.info(f"Cached diff to {diff_cache_file}: {len(diff_operations)} operations")
                                except Exception as e:
                                    app.logger.warning(f"Failed to cache diff: {e}")
                            except Exception as e:
                                app.logger.warning(f"Failed to calculate diff: {e}")
                
                all_history_list.append({
                    'changelist': changelist,
                    'revision': revision,
                    'time': record['time'],
                    'submitter': record['user'],
                    'description': record['description'],
                    'content': content,
                    'diffOperations': diff_operations
                })
            
            # 缓存全量结果
            latest_cl = int(p4Utils.get_latest_changelist(hotfixManifestP4File) or 0)
            full_result = {'all_history': all_history_list}
            _set_cached_p4_data(full_cache_key, hotfixManifestP4File, full_result, latest_cl)
            with _p4_data_cache_lock:
                if full_cache_key in _p4_data_cache:
                    _p4_data_cache[full_cache_key]['latest_cl'] = latest_cl
            
        except Exception as e:
            app.logger.error(f"getHotfixManifestHistory failed: {e}")
            return jsonify({'errMsg': str(e)}), 500
    
    # 分页返回
    total = len(all_history_list)
    start_idx = offset
    end_idx = min(offset + limit, total)
    
    paged_history = all_history_list[start_idx:end_idx] if start_idx < total else []
    
    return jsonify({
        'total': total,
        'history': paged_history
    })

@app.route('/clearHotfixManifestCache', methods=['POST'])
def clearHotfixManifestCache():
    """清除Hotfix Manifest历史记录的缓存
    
    参数:
        hotfixType: server/client/crates (可选，不提供则清除所有类型)
        env: prod/test (可选，不提供则清除所有环境)
    
    返回:
        {
            "success": true,
            "clearedMemoryKeys": [...],  // 清除的内存缓存key
            "clearedFiles": 10,          // 清除的文件数量
            "clearedDirs": 3             // 清除的目录数量
        }
    """
    app.logger.info("clearHotfixManifestCache")
    
    # 支持 query parameters 和 JSON body 两种方式
    hotfix_type = request.args.get('hotfixType') or (request.json.get('hotfixType') if request.json else None)
    env_value = request.args.get('env') or (request.json.get('env') if request.json else None)
    
    if env_value:
        env_value = _normalize_hotfix_env(env_value)
    
    # 清除内存缓存
    cleared_memory_keys = []
    with _p4_data_cache_lock:
        keys_to_remove = []
        for key in _p4_data_cache.keys():
            if key.startswith('manifest_history_full_'):
                # 检查是否匹配指定的 hotfixType 和 env
                should_clear = True
                if hotfix_type and f'_{hotfix_type}_' not in key:
                    should_clear = False
                if env_value and f'_{env_value}_' not in key:
                    should_clear = False
                
                if should_clear:
                    keys_to_remove.append(key)
                    cleared_memory_keys.append(key)
        
        for key in keys_to_remove:
            del _p4_data_cache[key]
    
    # 清除文件缓存
    cleared_files = 0
    cleared_dirs = 0
    
    hotfix_types = [hotfix_type] if hotfix_type else ['server', 'client', 'crates']
    env_suffixes = []
    if env_value is None:
        env_suffixes = ['', '_test']  # 清除所有环境
    elif env_value == 'test':
        env_suffixes = ['_test']
    else:  # prod
        env_suffixes = ['']
    
    for hf_type in hotfix_types:
        for env_suffix in env_suffixes:
            cache_dir = os.path.join(
                config.P4_WORKSPACE_DIRECTORY,
                'C7', 'Development', 'Weekly', 'Server', 'hotfix',
                f'{hf_type}_hotfix',
                f'.history_cache{env_suffix}'
            )
            
            if os.path.exists(cache_dir):
                # 清除 diffs 目录下的所有文件
                diff_cache_dir = os.path.join(cache_dir, 'diffs')
                if os.path.exists(diff_cache_dir):
                    for file in os.listdir(diff_cache_dir):
                        file_path = os.path.join(diff_cache_dir, file)
                        if os.path.isfile(file_path):
                            try:
                                os.remove(file_path)
                                cleared_files += 1
                            except Exception as e:
                                app.logger.warning(f"Failed to remove {file_path}: {e}")
                
                # 注意：不删除历史版本文件（manifest.json#N），只删除 diff 缓存
                # 因为历史版本文件下载成本较高，而 diff 可以快速重新计算
    
    app.logger.info(f"Cleared cache: {len(cleared_memory_keys)} memory keys, {cleared_files} files, {cleared_dirs} dirs")
    
    return jsonify({
        'success': True,
        'clearedMemoryKeys': cleared_memory_keys,
        'clearedFiles': cleared_files,
        'clearedDirs': cleared_dirs
    })


def _calculate_manifest_diff(prev_data, curr_data):
    """计算两个manifest版本之间的差异
    
    每个操作以 (FileName, EffectServers, EffectTags) 三元组作为唯一标识
    因为同一个 hotfix 文件可能有多个操作（例如同时应用到 preonline 和 online）
    
    Returns:
        List of diff operations: [
            {
                "type": "add",
                "diffInfo": [
                    {"FileName": "hotfix_xxx", "EffectServers": [...], "EffectTags": [...]},
                    ...
                ]
            },
            {
                "type": "remove",
                "diffInfo": [
                    {"FileName": "hotfix_yyy", "EffectServers": [...], "EffectTags": [...]},
                    ...
                ]
            }
        ]
    """
    def _make_operation_key(item):
        """为每个操作生成唯一key: (FileName, sorted_EffectServers, sorted_EffectTags)"""
        fname = item.get('FileName', '')
        servers = tuple(sorted(item.get('EffectServers', [])))
        tags = tuple(sorted(item.get('EffectTags', [])))
        return (fname, servers, tags)
    
    # 构建操作映射表 (key -> 完整item)
    prev_ops = {}
    for item in prev_data:
        key = _make_operation_key(item)
        prev_ops[key] = item
    
    curr_ops = {}
    for item in curr_data:
        key = _make_operation_key(item)
        curr_ops[key] = item
    
    # 收集新增和删除的条目
    added_items = []
    removed_items = []
    
    # 找出新增的操作
    for key in curr_ops:
        if key not in prev_ops:
            item = curr_ops[key]
            diff_item = {
                'FileName': item.get('FileName'),
                'EffectServers': item.get('EffectServers', []),
                'EffectTags': item.get('EffectTags', [])
            }
            # 如果有cmd字段（CPP Hotfix），也要包含进去
            if 'cmd' in item:
                diff_item['cmd'] = item['cmd']
            added_items.append(diff_item)
    
    # 找出删除的操作
    for key in prev_ops:
        if key not in curr_ops:
            item = prev_ops[key]
            diff_item = {
                'FileName': item.get('FileName'),
                'EffectServers': item.get('EffectServers', []),
                'EffectTags': item.get('EffectTags', [])
            }
            # 如果有cmd字段（CPP Hotfix），也要包含进去
            if 'cmd' in item:
                diff_item['cmd'] = item['cmd']
            removed_items.append(diff_item)
    
    # 构建结果
    diff_ops = []
    if added_items:
        diff_ops.append({
            'type': 'add',
            'diffInfo': added_items
        })
    if removed_items:
        diff_ops.append({
            'type': 'remove',
            'diffInfo': removed_items
        })
    
    return diff_ops

@app.route('/modifyHotfixManifest', methods=['POST'])
def modifyHotfixManifest():
    """
    修改 Hotfix Manifest 的接口（统一使用 operations 数组）
    
    请求参数：
    {
        "operations": [
            {
                "action": "add" | "modify" | "delete",
                "hotfixName": "hotfix文件名",
                "hotfixType": "server" | "client",
                "effectServers": ["c7_qa4"]  // add/modify 时必填，delete 时不需要
            },
            ...  // 可以有多个操作，支持混合 server 和 client
        ],
        "branchType": "weekly" | "mainline"
    }
    
    单个操作示例：
    {
        "operations": [{
            "action": "add",
            "hotfixName": "hotfix_001",
            "hotfixType": "server",
            "effectServers": ["c7_qa4"]
        }],
        "branchType": "weekly"
    }
    
    返回格式（统一格式，无论单类型还是多类型）：
    {
        "code": 0,
        "data": {
            "server": "[server manifest JSON]" | null,
            "client": "[client manifest JSON]" | null
        },
        "summary": {
            "server": {"added": 1, "modified": 0, "deleted": 0, "failed": 0},
            "client": {"added": 0, "modified": 0, "deleted": 0, "failed": 0},
            "total": 1
        },
        "message": "Batch completed: total 1 operations",
        "errors": null
    }
    
    说明：
    - data 中未操作的类型字段为 null
    - summary 中始终包含 server 和 client 的统计信息
    """
    app.logger.info("modifyHotfixManifest")
    
    data = request.get_json() or {}
    operations = data.get('operations')
    branch_type = data.get('branchType')
    env_value = _normalize_hotfix_env(data.get('env'))
    
    # 参数验证
    if not operations or not isinstance(operations, list) or len(operations) == 0:
        return jsonify({'code': -1, 'errMsg': 'operations is required and must be a non-empty array'}), 400
    
    if not branch_type:
        return jsonify({'code': -1, 'errMsg': 'branchType is required'}), 400
    
    return _execute_batch_operations(operations, branch_type, env_value=env_value)


def _load_manifest(hotfix_type, branch_type, env_value='prod'):
    """加载指定类型的 manifest"""
    try:
        p4_file, local_file, err_resp, err_code = _get_hotfix_manifest_paths(hotfix_type, branch_type, env_value=env_value)
        if err_resp is not None:
            return None, err_resp.get_json().get('errMsg', 'Invalid args')
        
        # 同步最新版本
        ret = p4Utils.update_file(p4_file, local_file, force=True, changelist=0)
        if not ret:
            return None, f'Failed to sync {hotfix_type} manifest from P4'
        
        with open(local_file, 'r', encoding='utf-8') as f:
            manifest_data = json.load(f)
        
        if not isinstance(manifest_data, list):
            return None, f'{hotfix_type} manifest is not an array'
        
        return manifest_data, None
    
    except Exception as e:
        return None, f'Failed to load {hotfix_type} manifest: {str(e)}'


def _execute_batch_operations(operations, branch_type, env_value='prod'):
    """执行批量操作，支持混合 server/client/crates"""
    # 按 hotfixType 分组
    groups = {'server': [], 'client': [], 'crates': []}
    
    for idx, op in enumerate(operations):
        hotfix_type = op.get('hotfixType')
        if not hotfix_type or hotfix_type not in ['server', 'client', 'crates']:
            return jsonify({'code': -1, 'errMsg': f'Operation {idx+1}: Invalid or missing hotfixType'}), 400
        groups[hotfix_type].append((idx, op))
    
    # 加载所需的 manifest
    manifests = {}
    for hotfix_type in ['server', 'client', 'crates']:
        if groups[hotfix_type]:
            manifest_data, error = _load_manifest(hotfix_type, branch_type, env_value=env_value)
            if error:
                return jsonify({'code': -1, 'errMsg': error}), 400
            manifests[hotfix_type] = manifest_data
    
    # 执行所有操作
    summary = {
        'server': {'added': 0, 'modified': 0, 'deleted': 0, 'failed': 0},
        'client': {'added': 0, 'modified': 0, 'deleted': 0, 'failed': 0},
        'crates': {'added': 0, 'modified': 0, 'deleted': 0, 'failed': 0},
        'total': len(operations)
    }
    errors = []
    
    for hotfix_type, ops in groups.items():
        if not ops:
            continue
        
        manifest_data = manifests[hotfix_type]
        
        for idx, op in ops:
            action = op.get('action')
            hotfix_name = op.get('hotfixName')
            effect_servers = op.get('effectServers')
            effect_tags = op.get('effectTags')
            
            if not action or action not in ['add', 'modify', 'delete']:
                errors.append(f"Operation {idx+1}: Invalid action")
                summary[hotfix_type]['failed'] += 1
                continue
            
            if not hotfix_name:
                errors.append(f"Operation {idx+1}: Missing hotfixName")
                summary[hotfix_type]['failed'] += 1
                continue
            
            # 如果传入的 hotfixName 带 .lua 后缀，自动去掉；若带其他后缀则报错
            _, ext = os.path.splitext(hotfix_name)
            if ext:
                if ext.lower() == '.lua':
                    hotfix_name = hotfix_name[:-len(ext)]
                else:
                    errors.append(f"Operation {idx+1}: hotfixName '{hotfix_name}' has invalid extension '{ext}', only .lua is allowed")
                    summary[hotfix_type]['failed'] += 1
                    continue
            
            try:
                if action == 'add':
                    if next((f for f in manifest_data if f.get('FileName') == hotfix_name), None):
                        errors.append(f"Operation {idx+1}: {hotfix_type} hotfix '{hotfix_name}' already exists")
                        summary[hotfix_type]['failed'] += 1
                        continue
                    has_servers = isinstance(effect_servers, list) and len(effect_servers) > 0
                    has_tags = isinstance(effect_tags, list) and len(effect_tags) > 0
                    if has_servers == has_tags:
                        errors.append(f"Operation {idx+1}: effectServers and effectTags are mutually exclusive, provide exactly one")
                        summary[hotfix_type]['failed'] += 1
                        continue
                    
                    item = {'FileName': hotfix_name}
                    if has_servers:
                        item['EffectServers'] = effect_servers
                    else:
                        item['EffectTags'] = effect_tags
                    manifest_data.append(item)
                    summary[hotfix_type]['added'] += 1
                
                elif action == 'modify':
                    existing = next((f for f in manifest_data if f.get('FileName') == hotfix_name), None)
                    if not existing:
                        errors.append(f"Operation {idx+1}: {hotfix_type} hotfix '{hotfix_name}' not found")
                        summary[hotfix_type]['failed'] += 1
                        continue
                    has_servers = isinstance(effect_servers, list) and len(effect_servers) > 0
                    has_tags = isinstance(effect_tags, list) and len(effect_tags) > 0
                    if has_servers == has_tags:
                        errors.append(f"Operation {idx+1}: effectServers and effectTags are mutually exclusive, provide exactly one")
                        summary[hotfix_type]['failed'] += 1
                        continue
                    
                    if has_servers:
                        existing['EffectServers'] = effect_servers
                        if 'EffectTags' in existing:
                            del existing['EffectTags']
                    else:
                        existing['EffectTags'] = effect_tags
                        if 'EffectServers' in existing:
                            del existing['EffectServers']
                    summary[hotfix_type]['modified'] += 1
                
                elif action == 'delete':
                    original_count = len(manifest_data)
                    manifest_data = [f for f in manifest_data if f.get('FileName') != hotfix_name]
                    manifests[hotfix_type] = manifest_data
                    
                    if len(manifest_data) == original_count:
                        errors.append(f"Operation {idx+1}: {hotfix_type} hotfix '{hotfix_name}' not found")
                        summary[hotfix_type]['failed'] += 1
                        continue
                    
                    summary[hotfix_type]['deleted'] += 1
            
            except Exception as e:
                errors.append(f"Operation {idx+1}: {str(e)}")
                summary[hotfix_type]['failed'] += 1
    
    # 如果有任何错误，直接返回失败
    if errors:
        return jsonify({'code': -1, 'errMsg': '; '.join(errors), 'errors': errors}), 400

    # 生成返回数据 - 统一返回格式，始终包含 server 和 client 字段
    result_data = {
        'server': None,
        'client': None,
        'crates': None
    }
    # 只更新实际操作的类型
    for hotfix_type in manifests.keys():
        result_data[hotfix_type] = json.dumps(manifests[hotfix_type], ensure_ascii=False, indent=2)
    
    # 冲突检测+Kim 通知已移除（由 hotfixDirWatcher 每 2 分钟定时检测，避免每次 manifest 操作触发全量 P4 sync）

    # 统一返回完整格式（无论单类型还是多类型）
    total_failed = summary['server']['failed'] + summary['client']['failed'] + summary['crates']['failed']
    return jsonify({
        'code': 0 if total_failed == 0 else 1,
        'data': result_data,
        'summary': summary,
        'message': f"Batch completed: total {summary['total']} operations",
        'errors': errors if errors else None,
    })


@app.route('/commitHotfixManifest', methods=['POST'])
def commitHotfixManifest():
    app.logger.info("commitHotfixManifest")

    data = request.get_json() or {}
    hotfixType = data.get('hotfixType')
    branchType = data.get('branchType') or 'weekly'
    env_value = _normalize_hotfix_env(data.get('env'))
    
    username = data.get('username') or 'unknown'
    description = data.get('description') or ''
    manifestCode = data.get('code')
    client_changelist = data.get('changelist')  # 前端提供的changelist
    
    branchType = 'weekly'
    jenkins_url = JENKINS_HOTFIX_STAGING_URL
    workspace = "hotfix_weekly_mini_workspace"

    app.logger.info(f"commitHotfixManifest: {hotfixType}, {branchType}, {workspace}, {username}, {description}, client_changelist: {client_changelist}")
    if not hotfixType or not branchType or not workspace or manifestCode is None or not description:
        return jsonify({'code': -1, 'errMsg': 'Missing hotfixType, branchType, workspace, data or description'}), 400

    hotfixManifestP4File, hotfixManifestLocalFile, errResp, errCode = _get_hotfix_manifest_paths(hotfixType, branchType, env_value=env_value)
    if errResp is not None:
        return errResp, errCode
    app.logger.info(f"czx commit hotfix manifest: {hotfixManifestP4File} {hotfixManifestLocalFile}")

    # 版本检查：获取当前最新的changelist
    code, out, err2 = _run_p4_cmd(['p4', 'changes', '-m1', hotfixManifestP4File])
    if code == 0 and out:
        # 解析最新的changelist号
        match = re.match(r'^Change (\d+)', out.strip())
        if match:
            latest_changelist = int(match.group(1))
            app.logger.info(f"Latest changelist for {hotfixManifestP4File}: {latest_changelist}, client provided: {client_changelist}")
            
            # 比对版本
            if client_changelist and int(client_changelist) != latest_changelist:
                app.logger.warning(f"Version conflict: client has {client_changelist}, latest is {latest_changelist}")
                return jsonify({
                    'code': -100,
                    'errMsg': 'Manifest file has been updated by others',
                    'clientChangelist': client_changelist,
                    'latestChangelist': latest_changelist,
                    'message': f'当前页面的manifest版本(CL{client_changelist})已过期，最新版本为CL{latest_changelist}，请刷新页面后重新编辑'
                }), 409  # 409 Conflict

    description = data.get('description')

    ok, err = _cleanup_workspace_pending(workspace)
    if not ok:
        app.logger.error(f"czx cleanup workspace pending failed: {err}")
        return jsonify({'code': -2, 'errMsg': err or 'cleanup workspace pending failed'}), 500

    app.logger.info(f"czx p4 cleanup success {workspace}")

    code, out, err2 = _run_p4_cmd(['p4', '-c', workspace, 'sync', '-f', hotfixManifestP4File])
    if code != 0:
        app.logger.error(f"czx p4 sync failed, try force sync: {err2 or out}")
        return jsonify({'code': -2, 'errMsg': err2 or out or 'p4 sync failed'}), 500

    app.logger.info(f"czx p4 sync success: {hotfixManifestP4File}")
    cl, err = _create_changelist(description, workspace=workspace)
    if not cl:
        app.logger.error(f"czx create changelist failed: {err or 'create changelist failed'}")
        return jsonify({'code': -3, 'errMsg': err or 'create changelist failed'}), 500
    app.logger.info(f"czx create changelist success: {cl}")

    code, out, err2 = _run_p4_cmd(['p4', '-c', workspace, 'edit', '-c', str(cl), hotfixManifestP4File])
    if code != 0:
        app.logger.error(f"czx p4 edit failed: {err2 or out}")
        return jsonify({'code': -4, 'errMsg': err2 or out or 'p4 edit failed', 'changelist': cl}), 500

    resolved_local_file = hotfixManifestLocalFile
    code, out, err2 = _run_p4_cmd(['p4', '-c', workspace, 'where', hotfixManifestP4File])
    if code == 0 and out:
        where_line = next((l.strip() for l in out.splitlines() if l.strip()), '')
        m = re.match(r'^(//\S+)\s+(//\S+)\s+(.+)$', where_line)
        if m:
            resolved_local_file = m.group(3).strip()
    app.logger.info(f"czx p4 where resolved local file: {resolved_local_file}")

    os.makedirs(os.path.dirname(resolved_local_file), exist_ok=True)
    with open(resolved_local_file, 'w', encoding='utf-8') as f:
        f.write(manifestCode)

    app.logger.info(f"czx write manifest code to local file success: {resolved_local_file}")

    code, out, err2 = _run_p4_cmd(['p4', '-c', workspace, 'opened', '-c', str(cl)])
    if code != 0:
        app.logger.error(f"czx p4 opened failed: {err2 or out}")
        return jsonify({'code': -4, 'errMsg': err2 or out or 'p4 opened failed', 'changelist': cl}), 500
    if not (out or '').strip():
        msg = f'changelist has no opened files: {cl}'
        app.logger.error(f"czx {msg}")
        return jsonify({'code': -4, 'errMsg': msg, 'changelist': cl}), 500

    code, out, err2 = _run_p4_cmd(['p4', '-c', workspace, 'diff', '-sa', hotfixManifestP4File])
    if code != 0 and not (out or '').strip() and (err2 or '').strip():
        app.logger.error(f"czx p4 diff failed: {err2 or out}")
        return jsonify({'code': -4, 'errMsg': err2 or out or 'p4 diff failed', 'changelist': cl}), 500
    if not (out or '').strip():
        # _run_p4_cmd(['p4', '-c', workspace, 'revert', '-c', str(cl), '//...'])
        # _run_p4_cmd(['p4', '-c', workspace, 'change', '-d', str(cl)])
        msg = 'No content changes, nothing to submit'
        app.logger.info(f"czx {msg}: {hotfixManifestP4File} out")
        return jsonify({'code': -6, 'msg': msg, 'changelist': cl, 'p4File': hotfixManifestP4File, 'jenkinsUrl': jenkins_url}), 200
    app.logger.info(f"czx p4 diff success: {hotfixManifestP4File}")
    code, out, err2 = _run_p4_cmd(['p4', '-c', workspace, 'submit', '-c', str(cl)])
    if code != 0:
        app.logger.error(f"czx p4 submit failed: {code} {err2 or out}")
        return jsonify({'code': -5, 'errMsg': err2 or out or 'p4 submit failed', 'changelist': cl}), 500

    # 解析最终提交的 CL 号
    submitted_cl = cl  # 默认用原来的
    match = re.search(r'renamed change (\d+) and submitted', out or '')
    if match:
        submitted_cl = int(match.group(1))
    else:
        # 兼容没有 rename 的情况（CL 号不变）
        match2 = re.search(r'Change (\d+) submitted', out or '')
        if match2:
            submitted_cl = int(match2.group(1))

    app.logger.info(f"czx p4 submit success: {hotfixManifestP4File} original cl: {cl}, submitted cl: {submitted_cl}")

    # 提交成功后，增量更新函数名索引
    try:
        import json as _json
        manifest_data_list = _json.loads(manifestCode) if isinstance(manifestCode, str) else manifestCode
        if isinstance(manifest_data_list, list):
            for item in manifest_data_list:
                fname = item.get('FileName', '')
                if fname and fname.startswith('hotfix_') and fname.endswith('.lua'):
                    lua_path = _get_hotfix_lua_local_path(fname, hotfixType, branchType)
                    if lua_path and os.path.exists(lua_path):
                        with open(lua_path, 'r', encoding='utf-8') as lf:
                            lua_content = lf.read()
                        _update_hotfix_func_index(fname, lua_content, hotfixType, branchType)
    except Exception as idx_err:
        app.logger.warning(f"auto update func index after commit failed (non-critical): {idx_err}")

    return jsonify({'code': 0, 'msg': 'Submit success', 'changelist': submitted_cl, 'p4File': hotfixManifestP4File, 'jenkinsUrl': jenkins_url})


@app.route('/commitHotfixManifestBatch', methods=['POST'])
def commitHotfixManifestBatch():
    """批量提交多个类型的manifest到同一个changelist"""
    data = request.get_json() or {}
    types = data.get('types', [])  # [{hotfixType, code, description, changelist}, ...]
    branchType = data.get('branchType') or 'weekly'
    env_value = _normalize_hotfix_env(data.get('env'))
    username = data.get('username') or 'unknown'
    description = data.get('description') or ''
    
    app.logger.info(f"commitHotfixManifestBatch - username: {username}, branchType: {branchType}, env: {env_value}, types: {[t.get('hotfixType') for t in types]}, description: {description}")
    
    if not types or not isinstance(types, list):
        app.logger.error("commitHotfixManifestBatch - Missing or invalid types parameter")
        return jsonify({'code': -1, 'errMsg': 'Missing or invalid types parameter'}), 400
    
    branchType = 'weekly'
    # 根据环境选择对应的Jenkins URL
    if env_value == 'prod':
        jenkins_url = JENKINS_HOTFIX_IDC_URL
    else:
        jenkins_url = JENKINS_HOTFIX_STAGING_URL
    workspace = "hotfix_weekly_mini_workspace"
    
    app.logger.info(f"commitHotfixManifestBatch - Using workspace: {workspace}, jenkins_url: {jenkins_url}, env: {env_value}")
    
    results = []
    files_to_process = []
    version_conflicts = []  # 记录版本冲突
    
    # Step 1: 收集所有需要处理的文件信息并检查版本
    app.logger.info("commitHotfixManifestBatch - Step 1: Collecting file information and checking versions")
    for type_info in types:
        hotfixType = type_info.get('hotfixType')
        manifestCode = type_info.get('code')
        type_desc = type_info.get('description', '')
        client_changelist = type_info.get('changelist')  # 前端提供的changelist
        
        app.logger.info(f"commitHotfixManifestBatch - Processing type: {hotfixType}, description: {type_desc}, client_changelist: {client_changelist}")
        
        if not hotfixType or manifestCode is None:
            app.logger.warning(f"commitHotfixManifestBatch - Missing hotfixType or code for type: {hotfixType}")
            results.append({
                'hotfixType': hotfixType,
                'success': False,
                'errMsg': 'Missing hotfixType or code'
            })
            continue
        
        try:
            hotfixManifestP4File, hotfixManifestLocalFile, errResp, errCode = _get_hotfix_manifest_paths(hotfixType, branchType, env_value=env_value)
            if errResp is not None:
                app.logger.error(f"commitHotfixManifestBatch - Invalid manifest path for {hotfixType}: {errResp.json}")
                results.append({
                    'hotfixType': hotfixType,
                    'success': False,
                    'errMsg': f'Invalid manifest path: {errResp.json}'
                })
                continue
            
            app.logger.info(f"commitHotfixManifestBatch - {hotfixType} P4 file: {hotfixManifestP4File}")
            
            # 版本检查：获取当前最新的changelist
            code, out, err2 = _run_p4_cmd(['p4', 'changes', '-m1', hotfixManifestP4File])
            if code == 0 and out:
                match = re.match(r'^Change (\d+)', out.strip())
                if match:
                    latest_changelist = int(match.group(1))
                    app.logger.info(f"Latest changelist for {hotfixType}: {latest_changelist}, client provided: {client_changelist}")
                    
                    # 比对版本
                    if client_changelist and int(client_changelist) != latest_changelist:
                        app.logger.warning(f"Version conflict for {hotfixType}: client has {client_changelist}, latest is {latest_changelist}")
                        version_conflicts.append({
                            'hotfixType': hotfixType,
                            'clientChangelist': client_changelist,
                            'latestChangelist': latest_changelist
                        })
                        continue  # 跳过有冲突的类型
            
            files_to_process.append({
                'hotfixType': hotfixType,
                'p4File': hotfixManifestP4File,
                'localFile': hotfixManifestLocalFile,
                'code': manifestCode,
                'description': type_desc
            })
            
        except Exception as e:
            app.logger.error(f"commitHotfixManifestBatch - Exception while collecting {hotfixType}: {e}")
            results.append({
                'hotfixType': hotfixType,
                'success': False,
                'errMsg': str(e)
            })
    
    # 如果有版本冲突，直接返回错误
    if version_conflicts:
        conflict_messages = []
        for conflict in version_conflicts:
            conflict_messages.append(
                f"{conflict['hotfixType']}: 当前页面版本CL{conflict['clientChangelist']}已过期，最新版本为CL{conflict['latestChangelist']}"
            )
        
        app.logger.error(f"commitHotfixManifestBatch - Version conflicts detected: {conflict_messages}")
        return jsonify({
            'code': -100,
            'errMsg': 'Manifest files have been updated by others',
            'conflicts': version_conflicts,
            'message': '部分manifest文件已被其他人更新，请刷新页面后重新编辑。\n' + '\n'.join(conflict_messages)
        }), 409  # 409 Conflict
    
    if not files_to_process:
        app.logger.warning("commitHotfixManifestBatch - No valid files to process")
        return jsonify({'code': -1, 'errMsg': 'No valid files to process', 'results': results}), 400
    
    # Step 2: 清理工作区
    app.logger.info("commitHotfixManifestBatch - Step 2: Cleaning workspace")
    ok, err = _cleanup_workspace_pending(workspace)
    if not ok:
        app.logger.error(f"commitHotfixManifestBatch - Workspace cleanup failed: {err}")
        return jsonify({'code': -1, 'errMsg': f'Workspace cleanup failed: {err}', 'results': results}), 500
    
    # Step 3: 同步所有文件
    app.logger.info("commitHotfixManifestBatch - Step 3: Syncing all files")
    for file_info in files_to_process:
        p4File = file_info['p4File']
        app.logger.info(f"commitHotfixManifestBatch - Syncing {p4File}")
        code, out, err2 = _run_p4_cmd(['p4', '-c', workspace, 'sync', '-f', p4File])
        if code != 0:
            app.logger.error(f"commitHotfixManifestBatch - P4 sync failed for {p4File}: {err2 or out}")
            results.append({
                'hotfixType': file_info['hotfixType'],
                'success': False,
                'errMsg': f'P4 sync failed: {err2 or out}'
            })
            continue
        file_info['syncSuccess'] = True
    
    # 过滤出同步成功的文件
    files_to_process = [f for f in files_to_process if f.get('syncSuccess')]
    
    if not files_to_process:
        app.logger.warning("commitHotfixManifestBatch - No files synced successfully")
        return jsonify({'code': -1, 'errMsg': 'All file syncs failed', 'results': results}), 500
    
    # Step 4: 创建单一changelist
    app.logger.info("commitHotfixManifestBatch - Step 4: Creating single changelist")
    cl_description = description if description else 'Batch commit hotfix manifests'
    cl, err = _create_changelist(cl_description, workspace=workspace)
    if not cl:
        app.logger.error(f"commitHotfixManifestBatch - Create changelist failed: {err}")
        return jsonify({'code': -1, 'errMsg': f'Create changelist failed: {err}', 'results': results}), 500
    
    app.logger.info(f"commitHotfixManifestBatch - Created changelist: {cl}")
    
    # Step 5: 编辑所有文件并写入内容
    app.logger.info("commitHotfixManifestBatch - Step 5: Editing files and writing content")
    files_with_changes = []
    
    for file_info in files_to_process:
        hotfixType = file_info['hotfixType']
        p4File = file_info['p4File']
        manifestCode = file_info['code']
        
        try:
            # Edit file
            app.logger.info(f"commitHotfixManifestBatch - Editing {p4File} in changelist {cl}")
            code, out, err2 = _run_p4_cmd(['p4', '-c', workspace, 'edit', '-c', str(cl), p4File])
            if code != 0:
                app.logger.error(f"commitHotfixManifestBatch - P4 edit failed for {p4File}: {err2 or out}")
                results.append({
                    'hotfixType': hotfixType,
                    'success': False,
                    'errMsg': f'P4 edit failed: {err2 or out}',
                    'changelist': cl
                })
                continue
            
            # Resolve local file path
            resolved_local_file = file_info['localFile']
            code, out, err2 = _run_p4_cmd(['p4', '-c', workspace, 'where', p4File])
            if code == 0 and out:
                where_line = next((l.strip() for l in out.splitlines() if l.strip()), '')
                m = re.match(r'^(//\S+)\s+(//\S+)\s+(.+)$', where_line)
                if m:
                    resolved_local_file = m.group(3).strip()
            
            app.logger.info(f"commitHotfixManifestBatch - Writing content to {resolved_local_file}")
            # Write manifest code
            os.makedirs(os.path.dirname(resolved_local_file), exist_ok=True)
            with open(resolved_local_file, 'w', encoding='utf-8') as f:
                f.write(manifestCode)
            
            # Check if there are changes
            code, out, err2 = _run_p4_cmd(['p4', '-c', workspace, 'diff', '-sa', p4File])
            if not (out or '').strip():
                app.logger.info(f"commitHotfixManifestBatch - No content changes for {p4File}, reverting")
                _run_p4_cmd(['p4', '-c', workspace, 'revert', '-c', str(cl), p4File])
                results.append({
                    'hotfixType': hotfixType,
                    'success': True,
                    'noChanges': True,
                    'message': 'No content changes'
                })
                continue
            
            app.logger.info(f"commitHotfixManifestBatch - {p4File} has changes, marking for submit")
            files_with_changes.append(file_info)
            
        except Exception as e:
            app.logger.error(f"commitHotfixManifestBatch - Exception while processing {hotfixType}: {e}")
            results.append({
                'hotfixType': hotfixType,
                'success': False,
                'errMsg': str(e)
            })
    
    # Step 6: 提交changelist
    if not files_with_changes:
        app.logger.info("commitHotfixManifestBatch - No files with changes, deleting changelist")
        _run_p4_cmd(['p4', '-c', workspace, 'change', '-d', str(cl)])
        
        # 检查是否全部是noChanges
        all_no_changes = all(r.get('noChanges') for r in results)
        if all_no_changes:
            app.logger.info("commitHotfixManifestBatch - All files have no changes")
            return jsonify({'code': 0, 'msg': 'No changes to submit', 'results': results, 'jenkinsUrl': jenkins_url})
        else:
            app.logger.warning("commitHotfixManifestBatch - All file processing failed")
            return jsonify({'code': -1, 'errMsg': 'All file processing failed', 'results': results}), 500
    
    app.logger.info(f"commitHotfixManifestBatch - Step 6: Submitting changelist {cl} with {len(files_with_changes)} files")
    code, out, err2 = _run_p4_cmd(['p4', '-c', workspace, 'submit', '-c', str(cl)])
    if code != 0:
        app.logger.error(f"commitHotfixManifestBatch - P4 submit failed: {err2 or out}")
        return jsonify({'code': -1, 'errMsg': f'P4 submit failed: {err2 or out}', 'changelist': cl, 'results': results}), 500
    
    # Parse submitted CL
    submitted_cl = cl
    match = re.search(r'renamed change (\d+) and submitted', out or '')
    if match:
        submitted_cl = int(match.group(1))
    
    app.logger.info(f"commitHotfixManifestBatch - Successfully submitted changelist: {submitted_cl}")
    
    # 为所有成功的文件添加结果
    for file_info in files_with_changes:
        results.append({
            'hotfixType': file_info['hotfixType'],
            'success': True,
            'changelist': submitted_cl,
            'p4File': file_info['p4File'],
            'jenkinsUrl': jenkins_url
        })
    
    app.logger.info(f"commitHotfixManifestBatch - Completed successfully, changelist: {submitted_cl}, results: {len(results)}")
    return jsonify({'code': 0, 'msg': 'Batch commit completed', 'results': results, 'jenkinsUrl': jenkins_url, 'changelist': submitted_cl})


@app.route('/buildHotfixFuncIndex', methods=['POST'])
def buildHotfixFuncIndex():
    """构建函数名索引（默认增量，forceFull=True时全量），异步执行，完成后Kim通知"""
    data = request.get_json() or {}
    side = data.get('side')
    branch_type = data.get('branchType', 'weekly')
    force_full = data.get('forceFull', False)
    notify_user = data.get('notifyUser', 'mengyun03')

    if not side or side not in ['server', 'client']:
        return jsonify({'code': -1, 'errMsg': 'Invalid side, must be server or client'}), 400

    try:
        started = _start_build_index(side, branch_type, force_full=force_full, notify_user=notify_user)
        if not started:
            return jsonify({'code': 0, 'building': True, 'message': '索引正在构建中，请稍后查询'})
        mode = "全量" if force_full else "增量"
        return jsonify({'code': 0, 'building': True, 'message': f'{mode}构建已启动 ({side}/{branch_type})，完成后将通知 {notify_user}'})
    except Exception as e:
        app.logger.error(f"buildHotfixFuncIndex failed: {e}")
        return jsonify({'code': -1, 'errMsg': str(e)}), 500


@app.route('/buildIndexStatus', methods=['GET'])
def buildIndexStatus():
    side = request.args.get('side')
    branch_type = request.args.get('branchType', 'weekly')
    index_type = request.args.get('type', 'func')

    if not side or side not in ['server', 'client']:
        return jsonify({'code': -1, 'errMsg': 'Invalid side, must be server or client'}), 400

    try:
        if index_type == 'func':
            building = _is_func_index_building(side, branch_type)
            if building:
                return jsonify({'code': 0, 'building': True, 'message': '索引正在构建中'})
            cached = _get_cached_index(side, branch_type)
            if cached:
                func_count = sum(len(v) for v in cached.values())
                return jsonify({'code': 0, 'building': False, 'message': '索引构建完成', 'files': len(cached), 'funcs': func_count})
            return jsonify({'code': 0, 'building': False, 'message': '索引未构建'})
        elif index_type == 'symbol':
            if _symbol_index_is_building:
                return jsonify({'code': 0, 'building': True, 'message': '索引正在构建中'})
            file_index, _ = _load_project_symbol_index(side, branch_type)
            if file_index:
                return jsonify({'code': 0, 'building': False, 'message': '索引构建完成', 'symbols': len(file_index)})
            return jsonify({'code': 0, 'building': False, 'message': '索引未构建'})
        else:
            return jsonify({'code': -1, 'errMsg': 'Invalid type, must be func or symbol'}), 400
    except Exception as e:
        return jsonify({'code': -1, 'errMsg': str(e)}), 500


@app.route('/buildProjectSymbolIndex', methods=['POST'])
def buildProjectSymbolIndex():
    """全量构建项目符号索引（函数名→原始文件路径）"""
    data = request.get_json() or {}
    side = data.get('side')
    branch_type = data.get('branchType', 'weekly')

    if not side or side not in ['server', 'client']:
        return jsonify({'code': -1, 'errMsg': 'Invalid side, must be server or client'}), 400

    try:
        if _symbol_index_is_building:
            return jsonify({'code': 0, 'building': True, 'message': '索引正在构建中，请稍后查询'})
        _async_build_project_symbol_index(side, branch_type)
        return jsonify({'code': 0, 'building': True, 'message': f'索引构建已启动 ({side}/{branch_type})，请稍后查询'})
    except Exception as e:
        app.logger.error(f"buildProjectSymbolIndex failed: {e}")
        return jsonify({'code': -1, 'errMsg': str(e)}), 500


@app.route('/getProjectSymbolIndex', methods=['GET'])
def getProjectSymbolIndex():
    """读取项目符号索引，返回文件名索引数据供前端展示"""
    side = request.args.get('side')
    branch_type = request.args.get('branchType', 'weekly')

    if not side or side not in ['server', 'client']:
        return jsonify({'code': -1, 'errMsg': 'Invalid side'}), 400

    try:
        file_index, needs_rebuild = _load_project_symbol_index(side, branch_type)
        if file_index is None:
            return jsonify({'code': 0, 'data': [], 'needs_rebuild': True, 'count': 0, 'message': '索引不存在，请先构建'})

        # 将 {norm_name: [p4_path, ...]} 展开为前端表格格式
        rows = []
        for norm_name, paths in file_index.items():
            for p4_path in paths:
                basename = p4_path.split('/')[-1]
                rows.append({'fileName': basename, 'normName': norm_name, 'filePath': p4_path})

        # 按文件名排序
        rows.sort(key=lambda x: x['fileName'].lower())

        return jsonify({
            'code': 0,
            'data': rows,
            'needs_rebuild': needs_rebuild,
            'count': len(rows),
        })
    except Exception as e:
        app.logger.error(f"getProjectSymbolIndex failed: {e}")
        return jsonify({'code': -1, 'errMsg': str(e)}), 500


@app.route('/findRelatedHotfixFiles', methods=['GET'])
def findRelatedHotfixFiles():
    """查找修改相同函数的关联 hotfix 文件"""
    file_name = request.args.get('fileName')
    side = request.args.get('side')
    branch_type = request.args.get('branchType', 'weekly')

    if not file_name or not side or side not in ['server', 'client']:
        return jsonify({'code': -1, 'errMsg': 'Missing fileName or invalid side'}), 400

    try:
        full_index = _get_cached_index(side, branch_type)
        if not full_index:
            index_file_path = _get_func_index_file_path(side, branch_type)
            if index_file_path and os.path.exists(index_file_path):
                with open(index_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                full_index = data.get('index', {})
                if full_index:
                    _set_cached_index(side, branch_type, full_index)
        if not full_index:
            if _is_func_index_building(side, branch_type):
                return jsonify({'code': 1, 'message': '索引正在构建中，请稍后重试'})
            _start_build_index(side, branch_type)
            return jsonify({'code': 1, 'message': '索引不存在，已触发构建，请稍后重试'})
        related = _find_related_hotfix_files(file_name, side, branch_type, full_index=full_index)
        return jsonify({'code': 0, 'fileName': file_name, 'relatedFiles': related})
    except Exception as e:
        app.logger.error(f"findRelatedHotfixFiles failed: {e}")
        return jsonify({'code': -1, 'errMsg': str(e)}), 500


@app.route('/classifyHotfixType', methods=['POST'])
def classifyHotfixType():
    """分析 hotfix lua 文件内容，返回分类结果和 tag"""
    data = request.get_json() or {}
    lua_content = data.get('luaContent')
    side = data.get('side')  # optional

    if not lua_content:
        return jsonify({'code': -1, 'errMsg': 'Missing luaContent'}), 400

    try:
        classify_result = _classify_hotfix_type(lua_content)
        tags = _generate_hotfix_type_tags(lua_content, side)
        return jsonify({'code': 0, 'classify': classify_result, 'tags': tags})
    except Exception as e:
        app.logger.error(f"classifyHotfixType failed: {e}")
        return jsonify({'code': -1, 'errMsg': str(e)}), 500


@app.route('/distillLuaForReview', methods=['POST'])
def distillLuaForReview():
    """对 lua 内容进行蒸馏，返回蒸馏结果和结构化摘要（调试用）"""
    data = request.get_json() or {}
    lua_content = data.get('luaContent')

    if not lua_content:
        return jsonify({'code': -1, 'errMsg': 'Missing luaContent'}), 400

    try:
        distill_result = _distill_lua_for_review(lua_content)
        return jsonify({'code': 0, 'distillResult': distill_result})
    except Exception as e:
        app.logger.error(f"distillLuaForReview failed: {e}")
        return jsonify({'code': -1, 'errMsg': str(e)}), 500


@app.route('/getLuaFileContent', methods=['GET'])
def getLuaFileContent():
    # 获取单个lua内容
    app.logger.info("czx getLuaFileContent")
    luaFilePath = request.args.get('luaFilePath')
    
    if not luaFilePath:
        return jsonify({
            'code': -1,
            'errMsg': '缺少参数luaFilePath',
            'fileContent': ''
        })
    
    # 检查是否是服务器端保存的文件
    if luaFilePath.startswith('uploads/'):
        try:
            server_file_path = os.path.join(os.path.dirname(__file__), '..', luaFilePath)
            with open(server_file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            return jsonify({
                'code': 0,
                'errMsg': '',
                'fileContent': file_content
            })
        except FileNotFoundError:
            return jsonify({
                'code': -1,
                'errMsg': f'服务器端文件不存在: {luaFilePath}',
                'fileContent': ''
            })
        except Exception as e:
            return jsonify({
                'code': -1,
                'errMsg': f'读取服务器端文件失败: {str(e)}',
                'fileContent': ''
            })
    else:
        # 使用P4路径获取文件
        luaFilePath = p4Utils.normalize_p4_path(luaFilePath)
        ret = p4Imp.getFileContent(luaFilePath)
        return jsonify(ret)

@app.route('/downloadUploadedFile', methods=['GET'])
def downloadUploadedFile():
    """下载上传的文件"""
    app.logger.info("czx downloadUploadedFile")
    
    try:
        file_path = request.args.get('filePath')
        
        if not file_path:
            return jsonify({
                'code': -1,
                'errMsg': '缺少参数filePath'
            }), 400
        
        # 检查是否是上传的文件路径
        if not file_path.startswith('uploads/'):
            return jsonify({
                'code': -1,
                'errMsg': '无效的文件路径，只能下载uploads目录下的文件'
            }), 400
        
        # 构建完整的服务器文件路径
        server_file_path = os.path.join(os.path.dirname(__file__), '..', file_path)
        
        # 检查文件是否存在
        if not os.path.exists(server_file_path):
            return jsonify({
                'code': -1,
                'errMsg': f'文件不存在: {file_path}'
            }), 404
        
        # 读取文件内容
        with open(server_file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        # 返回文件内容作为文本响应
        from flask import Response
        
        # 从文件路径中提取文件名
        file_name = os.path.basename(file_path)
        
        response = Response(
            file_content,
            mimetype='text/plain',
            headers={
                'Content-Disposition': f'attachment; filename="{file_name}"',
                'Content-Type': 'text/plain; charset=utf-8'
            }
        )
        
        app.logger.info(f"文件下载成功: {file_path}")
        return response
        
    except Exception as e:
        app.logger.error(f"文件下载失败: {str(e)}")
        return jsonify({
            'code': -1,
            'errMsg': f'文件下载失败: {str(e)}'
        }), 500

@app.route('/c7/runtime_struct', methods=['GET'])
def getC7RuntimeStruct():
    app.logger.info("getC7RuntimeStruct")
    try:
        target = request.args.get('target', 'server')
        file_name = 'serverRuntimeStruct.json' if target != 'client' else 'clientRuntimeStruct.json'
        file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'C7', file_name)
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({'msg': data, 'target': target})
    except FileNotFoundError:
        return jsonify({'msg': {}, 'errMsg': 'file not found'}), 404
    except Exception as e:
        return jsonify({'msg': {}, 'errMsg': str(e)}), 500


@cron('weekly sun 02:00')
def clearUploadsFile():
    app.logger.info("clearUploadsFile start")
    now_ts = datetime.now().timestamp()
    expire_seconds = 30 * 24 * 60 * 60
    expire_before = now_ts - expire_seconds

    uploads_dir = os.path.join(os.path.dirname(__file__), '..', 'uploads')
    uploads_dir = os.path.abspath(uploads_dir)

    if not os.path.exists(uploads_dir):
        return

    deleted_files = 0
    deleted_dirs = 0

    for root, dirs, files in os.walk(uploads_dir):
        for name in files:
            if name in ('.gitkeep',):
                continue
            file_path = os.path.join(root, name)
            try:
                st = os.stat(file_path)
                if st.st_mtime < expire_before:
                    os.remove(file_path)
                    deleted_files += 1
            except Exception as e:
                app.logger.error(f"clearUploadsFile failed: {file_path}, {str(e)}")

    for root, dirs, files in os.walk(uploads_dir, topdown=False):
        for name in dirs:
            dir_path = os.path.join(root, name)
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    deleted_dirs += 1
            except Exception as e:
                app.logger.error(f"clearUploadsFile remove dir failed: {dir_path}, {str(e)}")

    if deleted_files or deleted_dirs:
        app.logger.info(f"clearUploadsFile done: deleted_files={deleted_files} deleted_dirs={deleted_dirs}")
    app.logger.info("clearUploadsFile end")


@cron('weekly sun 02:00')
def clearP4Workspace():
    # 清空P4_WORKSPACE_DIRECTORY下一个月之前的所有文件
    app.logger.info("clearP4Workspace start")
    workspace_dir = config.P4_WORKSPACE_DIRECTORY
    workspace_dir = os.path.abspath(workspace_dir)
    if not os.path.exists(workspace_dir):
        app.logger.info(f"clearP4Workspace skipped: workspace not exists: {workspace_dir}")
        return

    now_ts = datetime.now().timestamp()
    expire_seconds = 30 * 24 * 60 * 60
    expire_before = now_ts - expire_seconds

    deleted_files = 0
    deleted_dirs = 0
    skipped_files = 0

    for root, dirs, files in os.walk(workspace_dir):
        for name in files:
            if name in ('.p4config', '.gitkeep'):
                skipped_files += 1
                continue
            file_path = os.path.join(root, name)
            try:
                st = os.stat(file_path)
                if st.st_mtime < expire_before:
                    os.remove(file_path)
                    deleted_files += 1
            except Exception as e:
                app.logger.error(f"clearP4Workspace failed: {file_path}, {str(e)}")

    for root, dirs, files in os.walk(workspace_dir, topdown=False):
        for name in dirs:
            dir_path = os.path.join(root, name)
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    deleted_dirs += 1
            except Exception as e:
                app.logger.error(f"clearP4Workspace remove dir failed: {dir_path}, {str(e)}")

    app.logger.info(f"clearP4Workspace done: deleted_files={deleted_files} deleted_dirs={deleted_dirs} skipped_files={skipped_files}")


# @cron('every 5 seconds')
# def printHelloEvery5Second():
#     app.logger.info("Hello, this is a scheduled job!")


# @cron('every 5 minutes')
# def testEvery5Minutes():
#     app.logger.info("Test function every 5 minutes")


# @cron('daily 00:00')
# def testDailyAtMidnight():
#     app.logger.info("Test function at midnight")


@app.route('/generateLuaHotfix', methods=['POST'])
def generateLuaHotfix():
    # 获取单个lua内容
    data = request.get_json()
    filePairs = data.get('filePairs')
    app.logger.info(f"czx generateLuaHotfix {filePairs}")
    hotfixPrepareInfo = []
    
    # 重复元素报错
    duplicateElements = [x for x in filePairs if filePairs.count(x) > 1]
    if duplicateElements:
        return jsonify({
            'code': -1,
            'errMsg': f'filePairs里有重复元素{duplicateElements[0]}',
            'fileContent': ''
        })

    for filePair in filePairs:
        rawFilePath = filePair.get('rawFileName', '')
        oldFilePath = filePair.get('oldFilePath')
        newFilePath = filePair.get('newFilePath')
        oldFileUploaded = filePair.get('oldFileUploaded', False)
        newFileUploaded = filePair.get('newFileUploaded', False)
        oldFileContent = filePair.get('oldFileContent', '')
        newFileContent = filePair.get('newFileContent', '')

        if not oldFilePath:
            return jsonify({
                'code': -1,
                'errMsg': '缺少参数oldFilePath',
                'fileContent': ''
            })
        if not newFilePath:
            return jsonify({
                'code': -1,
                'errMsg': '缺少参数newFilePath',
                'fileContent': ''
            })

        if rawFilePath == '':
            if not oldFilePath.startswith('uploads/'):
                rawFilePath = oldFilePath
            elif not newFilePath.startswith('uploads/'):
                rawFilePath = newFilePath
        if '#' in rawFilePath:
            rawFilePath = rawFilePath.split('#')[0]

        # 处理旧文件
        if oldFileUploaded and oldFileContent:
            # 使用上传的文件内容
            if not oldFileContent.strip():
                return jsonify({
                    'code': -1,
                    'errMsg': '上传的旧文件内容为空',
                    'fileContent': ''
                })
        elif oldFilePath.startswith('uploads/'):
            # 读取服务器端保存的文件
            try:
                server_file_path = os.path.join(os.path.dirname(__file__), '..', oldFilePath)
                with open(server_file_path, 'r', encoding='utf-8') as f:
                    oldFileContent = f.read()
                if not oldFileContent.strip():
                    return jsonify({
                        'code': -1,
                        'errMsg': '服务器端旧文件内容为空',
                        'fileContent': ''
                    })
            except FileNotFoundError:
                return jsonify({
                    'code': -1,
                    'errMsg': f'服务器端文件不存在: {oldFilePath}',
                    'fileContent': ''
                })
            except Exception as e:
                return jsonify({
                    'code': -1,
                    'errMsg': f'读取服务器端旧文件失败: {str(e)}',
                    'fileContent': ''
                })
        else:
            # 使用P4路径获取文件
            parsedOldPath = p4Utils.parse_p4_path(oldFilePath)
            if not parsedOldPath:
                return jsonify({
                    'code': -1,
                    'errMsg': 'oldFilePath格式错误',
                    'fileContent': ''
                })

            if parsedOldPath['ext'] != '.lua':
                return jsonify({
                    'code': -1,
                    'errMsg': 'oldFilePath不是lua文件',
                    'fileContent': ''
                })
            if not parsedOldPath['rev']:
                return jsonify({
                    'code': -1,
                    'errMsg': 'oldFilePath需要包含具体版本信息#',
                    'fileContent': ''
                })
            oldFilePath = p4Utils.normalize_p4_path(oldFilePath)

            fileRet = p4Imp.getFileContent(oldFilePath)
            if fileRet['code'] != 0:
                return jsonify(fileRet)
            oldFileContent = fileRet['fileContent']
            if not oldFileContent:
                return jsonify({
                    'code': -1,
                    'errMsg': 'oldFilePath文件内容为空',
                    'fileContent': ''
                })

        # 处理新文件
        if newFileUploaded and newFileContent:
            # 使用上传的文件内容
            if not newFileContent.strip():
                return jsonify({
                    'code': -1,
                    'errMsg': '上传的新文件内容为空',
                    'fileContent': ''
                })
        elif newFilePath.startswith('uploads/'):
            # 读取服务器端保存的文件
            try:
                server_file_path = os.path.join(os.path.dirname(__file__), '..', newFilePath)
                with open(server_file_path, 'r', encoding='utf-8') as f:
                    newFileContent = f.read()
                if not newFileContent.strip():
                    return jsonify({
                        'code': -1,
                        'errMsg': '服务器端新文件内容为空',
                        'fileContent': ''
                    })
            except FileNotFoundError:
                return jsonify({
                    'code': -1,
                    'errMsg': f'服务器端文件不存在: {newFilePath}',
                    'fileContent': ''
                })
            except Exception as e:
                return jsonify({
                    'code': -1,
                    'errMsg': f'读取服务器端新文件失败: {str(e)}',
                    'fileContent': ''
                })
        else:
            # 使用P4路径获取文件
            parsedNewPath = p4Utils.parse_p4_path(newFilePath)
            if not parsedNewPath:
                return jsonify({
                    'code': -1,
                    'errMsg': 'newFilePath格式错误',
                    'fileContent': ''
                })
            if parsedNewPath['ext'] != '.lua':
                return jsonify({
                    'code': -1,
                    'errMsg': 'newFilePath不是lua文件',
                    'fileContent': ''
                })
            if not parsedNewPath['rev']:
                return jsonify({
                    'code': -1,
                    'errMsg': 'newFilePath需要包含具体版本信息#',
                    'fileContent': ''
                })
            newFilePath = p4Utils.normalize_p4_path(newFilePath)

            fileRet = p4Imp.getFileContent(newFilePath)
            if fileRet['code'] != 0:
                return jsonify(fileRet)
            newFileContent = fileRet['fileContent']
            if not newFileContent:
                return jsonify({
                    'code': -1,
                    'errMsg': 'newFilePath文件内容为空',
                    'fileContent': ''
                })

        hotfixPrepareInfo.append({
            'rawFilePath': rawFilePath,
            'oldFilePath': oldFilePath,
            'newFilePath': newFilePath,
            'oldFileContent': oldFileContent,
            'newFileContent': newFileContent,
        })

    hotfixRet = hotfixImp.generateHotfix(hotfixPrepareInfo)
    
    # 生成路径相关的tags（flowchart, skill, space等）
    path_tags = _detect_tags_from_file_pairs(hotfixPrepareInfo)
    
    # 从diff_info中提取修改类型和字段tags
    diff_info_list = hotfixRet.pop('diffInfo', [])
    
    # 生成两个版本的diff tags：
    # 1. 存储版本：包含所有ID的完整tag（用于数据库存储和查询）
    storage_diff_tags = _extract_diff_tags(diff_info_list, max_tags=None, display_mode=False)
    
    # 2. 显示版本：每组最多显示3个ID（用于前端界面展示）
    display_diff_tags = _extract_diff_tags(diff_info_list, max_tags=None, display_mode=True)
    
    # 3. 内容标签：<table_name>_<row_id>，让人一眼看出修改了哪些数据对象
    content_tags = _extract_content_tags(diff_info_list)
    
    # 合并tags（路径tags在前，内容tags在后）
    all_tags_for_storage = path_tags + storage_diff_tags + content_tags  # 完整版本，用于存储
    display_tags = path_tags + display_diff_tags + content_tags          # 显示版本，用于界面
    
    # 返回两个版本：
    # - tags: 用于前端显示的版本（聚合后，每组最多3个ID）
    # - tags_full: 用于数据库存储的完整版本（所有ID）
    hotfixRet['tags'] = display_tags
    hotfixRet['tags_full'] = all_tags_for_storage
    hotfixRet['tags_count'] = len(all_tags_for_storage)  # 告诉前端总共有多少个tags
    return jsonify(hotfixRet)


# ===========================
# AI Code Review 接口
# ===========================

# Hotfix Review 时注入的 Skill 文件路径（Perforce 路径）
# 代理服务会通过 p4 print 读取这些文件并拼接到 prompt 前面作为系统上下文
# skill_dirs 中的目录会自动展开为其下所有文件（通过 p4 files 列举）
_HOTFIX_REVIEW_SKILL_DIRS = [
    '//C7/Development/Mainline/Server/script_lua/.agents/skills/hotfix-writer',
    '//C7/Development/Mainline/Server/script_lua/.agents/skills/code-review',
]
_HOTFIX_REVIEW_SKILL_FILES = []  # 也可单独指定文件，留空则只用目录

# 支持的 AI 模型白名单
SUPPORTED_AI_MODELS = [
    'wanqing/glm-5',
    'wanqing/kat-coder',
    'wanqing/claude-4.6-sonnet',
    'wanqing/kimi-k2.5',
]

@app.route('/aiReviewHotfix', methods=['POST'])
def aiReviewHotfix():
    """调用 flickcli 对 hotfix 代码进行 AI 审查（集成蒸馏+结构化摘要+原始函数体上下文）"""
    data = request.get_json()
    hotfix_content = data.get('hotfixContent', '')
    model = data.get('model', 'wanqing/glm-5')
    skip_distill = data.get('skipDistill', False)
    side = data.get('side', 'server')
    branch_type = data.get('branchType', 'weekly')

    # 模型白名单校验
    if model not in SUPPORTED_AI_MODELS:
        return jsonify({
            'code': -1,
            'errMsg': f'不支持的模型: {model}，可选值: {SUPPORTED_AI_MODELS}',
            'review': ''
        })

    if not hotfix_content or not hotfix_content.strip():
        return jsonify({
            'code': -1,
            'errMsg': 'hotfix内容为空，无法进行AI审查',
            'review': ''
        })

    # Step 1: 蒸馏 hotfix 内容（降级保障：skipDistill=True 时跳过）
    distill_info = None
    content_for_ai = hotfix_content
    summary_prefix = ''

    if not skip_distill:
        try:
            distill_result = _distill_lua_for_review(hotfix_content)
            content_for_ai = distill_result['distilled']
            distill_info = {
                'original_lines': distill_result['original_lines'],
                'distilled_lines': distill_result['distilled_lines'],
                'type': distill_result['type'],
                'type_display': _HOTFIX_TYPE_DISPLAY.get(distill_result['type'], distill_result['type']),
                'summary': distill_result['summary'],
                'distilled_content': content_for_ai,
            }
            summary_prefix = f"【Hotfix 摘要】\n{distill_result['summary']}\n\n"
            app.logger.info(f"aiReviewHotfix: distilled {distill_result['original_lines']} -> {distill_result['distilled_lines']} lines, type={distill_result['type']}")
        except Exception as e:
            app.logger.warning(f"aiReviewHotfix: distill failed, using original content: {e}")
            # 蒸馏失败时降级使用原始内容，不中断 Review 流程
            content_for_ai = hotfix_content

    # Step 1.5: 查找原始函数体（仅 modify_func 类型，skipOriginalFunc 时跳过）
    original_func_info = None
    original_func_block = ''
    skip_original_func = data.get('skipOriginalFunc', False)

    if (not skip_original_func
            and distill_info is not None
            and distill_info.get('type') == _HOTFIX_TYPE_FUNC_MOD):
        # 取 hotfix 中所有函数名（含 AI fallback 解析动态写法），逐个查找原始函数体（最多处理 3 个）
        file_name_for_log = data.get('fileName', 'unknown')
        func_names = _extract_func_names_with_ai_fallback(hotfix_content, file_name=file_name_for_log)
        original_func_parts = []
        original_func_info = {'found_funcs': [], 'not_found_funcs': []}
        for func_name in func_names:
            try:
                orig = _find_original_func_body(func_name, side, branch_type)
                if orig['found']:
                    original_func_parts.append(
                        f"--- 原始函数: {func_name} ---\n```lua\n{orig['func_body']}\n```"
                    )
                    original_func_info['found_funcs'].append({
                        'func_name': func_name,
                        'file_path': orig['file_path'],
                        'original_lines': orig['original_lines'],
                        'distilled_lines': orig['distilled_lines'],
                        'func_body': orig['func_body'],
                    })
                    # 同步更新结构化摘要
                    summary_prefix += f"【原始函数来源】{orig['file_path'].split('/')[-1]}（蒸馏后 {orig['distilled_lines']} 行）\n"
                else:
                    original_func_info['not_found_funcs'].append(func_name)
                    summary_prefix += f"【原始函数】{func_name} 未找到（项目符号索引无记录，请手动确认）\n"
            except Exception as e:
                app.logger.warning(f"aiReviewHotfix: _find_original_func_body failed for {func_name}: {e}")
                original_func_info['not_found_funcs'].append(func_name)

        if original_func_parts:
            original_func_block = '\n\n'.join(original_func_parts) + '\n\n'

    # Step 2: 构造 AI prompt（含结构化摘要 + 原始函数体 + hotfix 代码）
    prompt = (
        f"{summary_prefix}\n"
        "你是一名资深 Lua 游戏开发工程师，请对以下 hotfix 补丁代码进行 code review。\n"
        "请严格按照以下 Markdown 格式输出：\n"
        "## Code Review 结果\n\n"
        "### 1. 潜在的 bug 或逻辑错误\n"
        "- （列举问题，无问题则写「无」）\n\n"
        "### 2. 崩溃/数据风险\n"
        "- （列举风险，无风险则写「无」）\n\n"
        "### 3. hotfix 方式评估\n"
        "- （评估是否合理）\n\n"
        "### 4. 改进建议\n"
        "（如有代码改进，必须用 ```lua 代码块 ``` 格式输出完整改进代码）\n\n"
        + (f"原始函数体（供对比参考，了解 hotfix 替换了什么）：\n{original_func_block}" if original_func_block else "")
        + f"hotfix 代码如下：\n```lua\n{content_for_ai}\n```"
    )

    # Step 3: 调用宿主机 flickcli 代理服务
    # 代理服务运行在宿主机上，避免容器内 flickcli 凭证问题
    # 代理脚本：server/docs/flickcli_proxy.py，启动方式见 server/docs/flickcli-linux-setup.md
    import urllib.request
    try:
        # 创建不使用代理的 opener，绕过容器内 HTTP_PROXY
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        urllib.request.install_opener(opener)
        req_data = json.dumps({'prompt': prompt, 'model': model, 'skill_paths': _HOTFIX_REVIEW_SKILL_FILES, 'skill_dirs': _HOTFIX_REVIEW_SKILL_DIRS}, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            _FLICKCLI_PROXY_URL,
            data=req_data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=130) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        if result.get('code') == 0:
            response_data = {
                'code': 0,
                'review': result.get('review', ''),
                'model': model,
                'distillInfo': distill_info,
                'originalFuncInfo': original_func_info,
            }
            return jsonify(response_data)
        else:
            return jsonify({'code': -1, 'errMsg': result.get('errMsg', 'AI 审查失败'), 'review': '', 'distillInfo': distill_info, 'originalFuncInfo': original_func_info})
    except Exception as e:
        app.logger.error(f'aiReviewHotfix proxy error: {str(e)}')
        return jsonify({'code': -1, 'errMsg': f'AI 审查异常: {str(e)}', 'review': '', 'distillInfo': distill_info})


# ===========================
# Hotfix 冲突信息接口（Phase 4）— Kim 消息通知 + 实时冲突检测
# ===========================

def _extract_hotfix_ticket_key(filename):
    """
    从 hotfix 文件名中提取 (author, redmine_id) 作为票据键。
    规则：hotfix_{name}_{redmineId}.lua 或 hotfix_{name}_{redmineId}_{n}.lua
    相同 author + redmine_id 视为同一个单子（同单同人），属于合理的多次提交，不算冲突。

    Returns: (author, redmine_id) or None
    """
    name = re.sub(r'\.lua$', '', os.path.basename(filename), flags=re.IGNORECASE)
    # 匹配 hotfix_{name}_{redmineId} 或 hotfix_{name}_{redmineId}_{n}
    m = re.match(r'^hotfix_(.+?)_(\d{5,7})(?:_\d+)?$', name)
    if m:
        return (m.group(1).lower(), m.group(2))
    return None


def _is_same_ticket(fname_a, fname_b):
    """
    判断两个 hotfix 文件是否属于同一个单子（同 author + 同 redmine_id）。
    是则返回 True，表示这对冲突可以豁免，不触发告警。
    """
    key_a = _extract_hotfix_ticket_key(fname_a)
    key_b = _extract_hotfix_ticket_key(fname_b)
    if key_a is None or key_b is None:
        return False
    return key_a == key_b


def _get_all_conflicts_from_index(side, branch_type):
    """
    从本地 func index JSON 读取索引，计算所有有冲突的文件对。
    同一 author + 同一 redmine_id 的文件对（同单同人多次提交）视为合理，不计入冲突。

    Returns: dict {fileName: {"conflicts": [{"func_name": "...", "conflicting_files": [...]}], ...}}
    """
    index_file_path = _get_func_index_file_path(side, branch_type)
    full_index = {}
    if index_file_path and os.path.exists(index_file_path):
        with open(index_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        full_index = data.get('index', {})

    if not full_index:
        return {}

    # 构建反向索引：func_name -> list of files
    func_to_files = {}
    for fname, func_names in full_index.items():
        for fn in func_names:
            if fn not in func_to_files:
                func_to_files[fn] = []
            func_to_files[fn].append(fname)

    # 找出所有有冲突的文件（同函数被多个文件修改）
    # 过滤：同 author + 同 redmine_id 的文件对视为同单同人，豁免不算冲突
    # 同时用带 .lua 和不带 .lua 的 key 存储，确保前端查找兼容
    conflicts_map = {}
    for func_name, files in func_to_files.items():
        if len(files) <= 1:
            continue
        for fname in files:
            # 排除同单同人的文件，只保留真正不同单/不同人的冲突文件
            real_conflict_files = [f for f in files if f != fname and not _is_same_ticket(fname, f)]
            if not real_conflict_files:
                continue
            if fname not in conflicts_map:
                conflicts_map[fname] = {"conflicts": [], "side": side, "branch_type": branch_type}
            # 同时注册不带 .lua 的 key（前端 Manifest FileName 不带 .lua）
            fname_no_ext = os.path.splitext(fname)[0]
            if fname_no_ext != fname and fname_no_ext not in conflicts_map:
                conflicts_map[fname_no_ext] = conflicts_map[fname]
            # 避免重复添加
            existing_funcs = {c['func_name'] for c in conflicts_map[fname]["conflicts"]}
            if func_name not in existing_funcs:
                conflicts_map[fname]["conflicts"].append({
                    "func_name": func_name,
                    "conflicting_files": real_conflict_files,
                })

    return conflicts_map


def _detect_and_notify_conflicts(file_names, side, branch_type, trigger_source='manifest', current_username=None):
    """
    对一组 hotfix 文件做冲突检测，若有冲突则即时发送 Kim 消息

    Args:
        file_names: list[str]，要检测的 hotfix 文件名（带或不带 .lua 都可）
        side: 'server' | 'client'
        branch_type: 'weekly' | 'mainline'
        trigger_source: 触发来源（用于消息标题区分），如 'manifest' / 'submit'
        current_username: 当前操作用户名（也会被通知到）

    Returns: dict {detected: int, notified_authors: list, conflicts: list}
    """
    summary = {'detected': 0, 'notified_authors': [], 'conflicts': []}
    if not file_names or side not in ('server', 'client'):
        return summary

    try:
        conflicts_map = _get_all_conflicts_from_index(side, branch_type)
    except Exception as e:
        app.logger.warning(f"_detect_and_notify_conflicts: get conflicts failed: {e}")
        return summary

    # 过滤出本次涉及的、且确实有冲突的文件
    triggered = {}  # display_name -> conflict_entry
    for raw in file_names:
        if not raw:
            continue
        # 兼容带/不带 .lua
        candidates = [raw, raw + '.lua', os.path.splitext(raw)[0]]
        entry = None
        display_name = raw
        for k in candidates:
            if k in conflicts_map and conflicts_map[k].get('conflicts'):
                entry = conflicts_map[k]
                display_name = k
                break
        if entry:
            triggered[display_name] = entry

    if not triggered:
        return summary

    # 拿提交人 author 信息
    branch_dir = _branch_dir_name(branch_type)
    if side == 'server':
        p4_dir = f"//C7/Development/{branch_dir}/Server/hotfix/server_hotfix/"
    else:
        p4_dir = f"//C7/Development/{branch_dir}/Server/hotfix/client_hotfix/"
    try:
        hotfix_list = p4Utils.list_dir(p4_dir)
    except Exception:
        hotfix_list = []
    author_map = {}
    cl_map = {}
    for f in hotfix_list:
        raw_name = f.get('name', '')
        if not raw_name:
            continue
        basename = os.path.splitext(os.path.basename(raw_name))[0]
        author = f.get('author', '')
        if author:
            author_map[basename] = author
            author_map[basename + '.lua'] = author
            author_map[raw_name] = author
        cl = f.get('changelist', 0) or 0
        if cl:
            cl_map[basename] = cl
            cl_map[basename + '.lua'] = cl
            cl_map[raw_name] = cl

    # 收集每个 hotfix 文件对应的 redmine 单号（来自其最近 CL 的提交描述）
    file_to_redmine_ids = {}  # file_name -> [issue_id, ...]
    try:
        from Implement.hotfixImpl.redmineMgr import RedmineMgr
        redmine_mgr = RedmineMgr()
    except Exception as e:
        app.logger.warning(f"_detect_and_notify_conflicts: import RedmineMgr failed: {e}")
        redmine_mgr = None

    def _resolve_redmine_ids(_fname):
        if _fname in file_to_redmine_ids:
            return file_to_redmine_ids[_fname]
        cl = cl_map.get(_fname) or cl_map.get(os.path.splitext(_fname)[0])
        ids = []
        if cl:
            try:
                desc = p4Utils.get_changelist_description(cl)
                if desc and redmine_mgr:
                    ids = redmine_mgr.extract_issue_ids_from_text(desc)
            except Exception as _e:
                app.logger.warning(f"resolve redmine ids for {_fname} cl={cl} failed: {_e}")
        file_to_redmine_ids[_fname] = ids
        return ids

    title_map = {
        'manifest': '⚠️ Hotfix Manifest 生成时检测到函数冲突（正在测试 请忽略）',
        'submit':   '⚠️ Hotfix 提交后检测到函数冲突（正在测试 请忽略）',
    }
    title = title_map.get(trigger_source, '⚠️ Hotfix 函数冲突警告')

    all_notified = set()
    all_conflicts_for_return = []
    new_conflict_keys = []
    seen_new_keys = set()
    qa_resolved_ids = set()
    issue_to_qa_kims = {}
    try:
        from Implement.hotfixImpl.c7KimRobot import C7KimRobot
        kim_robot = C7KimRobot()
    except Exception as e:
        app.logger.warning(f"_detect_and_notify_conflicts: import C7KimRobot failed: {e}")
        kim_robot = None

    try:
        from Implement.hotfixImpl.hotfixDirWatcher import _load_notified_conflicts, _save_notified_conflicts, _make_conflict_key, _get_mongo
        notified_conflicts = _load_notified_conflicts()
    except Exception as e:
        app.logger.warning(f"_detect_and_notify_conflicts: load notified conflicts failed: {e}")
        notified_conflicts = {}

    def _resolve_qa_kims(_rid):
        if _rid in qa_resolved_ids:
            return issue_to_qa_kims.get(_rid, [])
        qa_resolved_ids.add(_rid)
        kims = []
        if redmine_mgr:
            try:
                info = redmine_mgr.get_issue(_rid)
                if info:
                    kims = redmine_mgr.get_qa_kim_usernames(info)
            except Exception as _e:
                app.logger.warning(f"resolve qa for issue {_rid} failed: {_e}")
        issue_to_qa_kims[_rid] = kims
        return kims

    for fname, entry in triggered.items():
        conflict_lines = []
        target_authors = set()
        related_redmine_ids = set()
        for rid in _resolve_redmine_ids(fname):
            related_redmine_ids.add(rid)

        for c in entry.get('conflicts', []):
            func_name = c.get('func_name', '')
            other_files = c.get('conflicting_files', []) or []
            conflict_lines.append(
                f"- 函数 `{func_name}` 与以下文件同时修改：{', '.join(other_files)}"
            )
            all_conflicts_for_return.append({
                'file_name': fname,
                'func_name': func_name,
                'conflicting_files': other_files,
            })
            all_files = sorted([fname] + [f for f in other_files if f != fname])
            try:
                ckey = _make_conflict_key(side, branch_type, func_name, all_files)
            except Exception:
                ckey = None
            if ckey and ckey not in notified_conflicts and ckey not in seen_new_keys:
                seen_new_keys.add(ckey)
                new_conflict_keys.append({'key': ckey, 'func_name': func_name, 'conflicting_files': all_files})
            for cf in other_files:
                au = author_map.get(cf) or author_map.get(os.path.splitext(cf)[0])
                if au:
                    target_authors.add(au)
                for rid in _resolve_redmine_ids(cf):
                    related_redmine_ids.add(rid)

        # 通知本次操作者
        cur_au = author_map.get(fname) or author_map.get(os.path.splitext(fname)[0]) or current_username
        if cur_au:
            target_authors.add(cur_au)

        # 把所有关联 redmine 单的 QA（邮箱前缀）也加入 Kim 通知集合
        qa_kim_users = set()
        for rid in related_redmine_ids:
            for ku in _resolve_qa_kims(rid):
                qa_kim_users.add(ku)
                target_authors.add(ku)

        # 构造 redmine 链接片段
        redmine_link_lines = []
        if related_redmine_ids and redmine_mgr:
            for rid in sorted(related_redmine_ids):
                redmine_link_lines.append(f"- {redmine_mgr.REDMINE_URL}issues/{rid}")

        msg_body = (
            f"**{title}**\n\n"
            f"文件 `{fname}` 在 `{side}/{branch_type}` 中存在函数冲突：\n\n"
            + "\n".join(conflict_lines)
        )
        if current_username:
            msg_body += f"\n\n本次操作人：`{current_username}`"
        if redmine_link_lines:
            msg_body += "\n\n关联 Redmine 单号：\n" + "\n".join(redmine_link_lines)
        if qa_kim_users:
            msg_body += "\n\n关联 QA：" + ", ".join(f"@{u}" for u in sorted(qa_kim_users))

        if kim_robot and new_conflict_keys:
            for au in sorted(target_authors):
                ok, err = kim_robot.send_msg_to_user(au, msg_body)
                if ok:
                    all_notified.add(au)
                else:
                    app.logger.warning(f"_detect_and_notify_conflicts: notify {au} failed: {err}")

            for ck in new_conflict_keys:
                record = {
                    'func_name': ck['func_name'],
                    'side': side,
                    'branch_type': branch_type,
                    'conflicting_files': ck['conflicting_files'],
                    'notified_at': datetime.now().isoformat(),
                    'notified_authors': sorted(target_authors),
                    'trigger_source': trigger_source,
                }
                notified_conflicts[ck['key']] = record
                try:
                    mongo = _get_mongo()
                    if mongo is not None:
                        mongo.upsert_notified_conflict(ck['key'], record)
                except Exception as _e:
                    app.logger.warning(f"_detect_and_notify_conflicts: save notified conflict to mongo failed: {_e}")

        if kim_robot and new_conflict_keys:
            try:
                from Implement.hotfixImpl.hotfixDirWatcher import _load_notify_group_ids
                group_ids = _load_notify_group_ids()
            except Exception:
                group_ids = []
            for gid in group_ids:
                ok, err = kim_robot.send_msg_to_group(gid, msg_body)
                if ok:
                    app.logger.info(f"_detect_and_notify_conflicts: notified group {gid} for {fname}")
                else:
                    app.logger.warning(f"_detect_and_notify_conflicts: notify group {gid} failed: {err}")

    try:
        _save_notified_conflicts(notified_conflicts)
    except Exception as _e:
        app.logger.warning(f"_detect_and_notify_conflicts: save notified conflicts failed: {_e}")

    summary['detected'] = len(triggered)
    summary['notified_authors'] = sorted(all_notified)
    summary['conflicts'] = all_conflicts_for_return
    summary['notified_qas'] = sorted({u for kims in issue_to_qa_kims.values() for u in kims})
    app.logger.info(
        f"_detect_and_notify_conflicts: source={trigger_source}, side={side}/{branch_type}, "
        f"files={list(triggered.keys())}, authors={summary['notified_authors']}, "
        f"qas={summary['notified_qas']}"
    )
    return summary


@app.route('/getAllHotfixConflicts', methods=['GET'])
def getAllHotfixConflicts():
    """
    从 func index 实时计算所有冲突信息（不依赖 DB）

    请求参数：
    - side: 'server' | 'client'
    - branchType: 'weekly' | 'mainline'
    """
    side = request.args.get('side')
    branch_type = _normalize_branch_type(request.args.get('branchType'))

    if not side or side not in ['server', 'client']:
        return jsonify({'code': -1, 'errMsg': 'Missing or invalid side'}), 400

    cache_key = f"conflicts_{side}_{branch_type}"
    
    try:
        # 检查索引文件的修改时间戳，决定是否使用缓存
        index_file_path = _get_func_index_file_path(side, branch_type)
        current_index_mtime = 0
        if index_file_path and os.path.exists(index_file_path):
            try:
                current_index_mtime = os.path.getmtime(index_file_path)
            except Exception as e:
                app.logger.warning(f"getAllHotfixConflicts: get index mtime failed: {e}")
        
        # 尝试从缓存读取
        cached_entry = _get_cached_p4_data(cache_key, skip_cl_check=True)
        if cached_entry and cached_entry.get('changelist') == current_index_mtime:
            app.logger.debug(f"Conflicts cache hit: {cache_key} @ index mtime {current_index_mtime}")
            return jsonify(cached_entry['data'])
        
        # 计算冲突
        conflicts_map = _get_all_conflicts_from_index(side, branch_type)
        result = {'code': 0, 'data': conflicts_map}
        
        # 缓存结果（用 mtime 作为版本标识）
        _set_cached_p4_data(cache_key, index_file_path, result, current_index_mtime)
        
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"getAllHotfixConflicts failed: {e}")
        return jsonify({'code': -1, 'errMsg': str(e)}), 500


@app.route('/checkHotfixConflictByContent', methods=['POST'])
def checkHotfixConflictByContent():
    """
    根据传入的 lua 文件内容，实时提取函数名并与已有索引对比，检查是否存在冲突。
    适用于未提交文件，只需提供文件内容即可检测冲突。
    检测到冲突时自动发送 Kim 消息通知相关提交人。

    请求参数：
    {
        "luaContent": "lua文件的文本内容",
        "fileName": "hotfix_xxx.lua",     // 可选，用于日志和结果标识
        "side": "server" | "client",
        "branchType": "weekly" | "mainline"
    }

    返回：
    {
        "code": 0,
        "fileName": "...",
        "funcNames": ["ClassName.MethodName", ...],
        "conflicts": [{"funcName": "...", "conflictingFiles": [...]}],
        "notifiedAuthors": [...],
        "notifyResults": [...]
    }
    """
    from Implement.hotfixImpl import hotfixConflictChecker as hcc

    data = request.get_json() or {}
    lua_content = data.get('luaContent')
    file_name = data.get('fileName', 'unknown')
    side = data.get('side')
    branch_type = _normalize_branch_type(data.get('branchType'))

    if not lua_content:
        return jsonify({'code': -1, 'errMsg': 'Missing luaContent'}), 400
    if not side or side not in ['server', 'client']:
        return jsonify({'code': -1, 'errMsg': 'Missing or invalid side'}), 400

    try:
        # 优先从内存缓存读取，避免频繁读文件
        full_index = _get_cached_index(side, branch_type)
        if not full_index:
            index_file_path = _get_func_index_file_path(side, branch_type)
            full_index = hcc.load_func_index_from_file(index_file_path)
            if full_index:
                _set_cached_index(side, branch_type, full_index)
        if not full_index:
            if not _is_func_index_building(side, branch_type):
                _start_build_index(side, branch_type, notify=False)
            return jsonify({'code': 1, 'message': '索引不存在，已触发构建，请稍后重试'})

        func_names = _extract_func_names_from_lua(lua_content)
        if not func_names:
            return jsonify({
                'code': 0,
                'fileName': file_name,
                'funcNames': [],
                'conflicts': [],
                'message': 'No func_mod patterns found in the provided content'
            })

        result = hcc.check_by_content(
            lua_content=lua_content,
            file_name=file_name,
            side=side,
            branch_type=branch_type,
            full_index=full_index,
            extract_func_names_fn=_extract_func_names_from_lua,
            notify=True,
            app_logger=app.logger,
        )
        return jsonify({'code': 0, 'fileName': file_name, **result})
    except Exception as e:
        app.logger.error(f"checkHotfixConflictByContent failed: {e}")
        return jsonify({'code': -1, 'errMsg': str(e)}), 500


@app.route('/checkHotfixConflictByChangelist', methods=['POST'])
def checkHotfixConflictByChangelist():
    """
    根据 P4 pending changelist 号，获取该 CL 中所有 lua 文件内容，
    提取函数名并与已有索引对比，检查是否存在冲突。
    自动根据文件路径（server_hotfix / client_hotfix）区分 side，
    无需手动指定 side，同一 CL 中同时含 server 和 client 文件也能正确处理。
    检测到冲突时自动发送 Kim 消息通知相关提交人。

    请求参数：
    {
        "changelist": 12345,
        "branchType": "weekly" | "mainline",  // 可选，默认 weekly
        "side": "server" | "client"           // 可选，不传则根据路径自动推断
    }

    返回：
    {
        "code": 0,
        "changelist": 12345,
        "files": [{"fileName":..., "side":..., "funcNames":[...], "conflicts":[...]}],
        "hasConflict": true,
        "notifiedAuthors": [...],
        "notifyResults": [...]
    }
    """
    from Implement.hotfixImpl import hotfixConflictChecker as hcc

    data = request.get_json() or {}
    changelist = data.get('changelist')
    forced_side = data.get('side')
    branch_type = _normalize_branch_type(data.get('branchType'))

    if not changelist:
        return jsonify({'code': -1, 'errMsg': 'Missing changelist'}), 400
    try:
        changelist = int(changelist)
    except (TypeError, ValueError):
        return jsonify({'code': -1, 'errMsg': f'Invalid changelist: {changelist}'}), 400
    if forced_side and forced_side not in ['server', 'client']:
        return jsonify({'code': -1, 'errMsg': f'Invalid side: {forced_side}'}), 400

    _index_unavailable_for = {}

    def _get_index(side, bt):
        full_index = _get_cached_index(side, bt)
        if not full_index:
            index_file_path = _get_func_index_file_path(side, bt)
            full_index = hcc.load_func_index_from_file(index_file_path)
            if full_index:
                _set_cached_index(side, bt, full_index)
        if not full_index:
            _index_unavailable_for[f"{side}/{bt}"] = True
            if not _is_func_index_building(side, bt):
                _start_build_index(side, bt, notify=False)
        return full_index

    try:
        if side == 'server':
            p4_dir = f"//C7/Development/{branch_dir}/Server/hotfix/server_hotfix/"
        else:
            p4_dir = f"//C7/Development/{branch_dir}/Server/hotfix/client_hotfix/"

        hotfix_list = p4Utils.list_dir(p4_dir)
        author_map = {}
        for f in hotfix_list:
            raw_name = f.get('name', '')
            if not raw_name:
                continue
            basename = os.path.splitext(os.path.basename(raw_name))[0]
            author = f.get('author', '')
            if author:
                author_map[basename] = author
                author_map[basename + '.lua'] = author
                author_map[raw_name] = author

        conflict_desc_lines = []
        notified_authors = set()
        for c in formatted_conflicts:
            line = f"- 函数 `{c['func_name']}` 被以下文件同时修改：{', '.join(c['conflicting_files'])}"
            conflict_desc_lines.append(line)
            for cf in c['conflicting_files']:
                author = author_map.get(cf) or author_map.get(os.path.splitext(cf)[0])
                if author:
                    notified_authors.add(author)

        msg_body = f"**⚠️ Hotfix 函数冲突警告**\n\n"
        msg_body += f"文件 `{file_name}` 在 `{side}/{branch_type}` 中存在函数冲突：\n\n"
        msg_body += "\n".join(conflict_desc_lines)
        if ai_review_summary:
            msg_body += f"\n\n**AI Review 概要**: {ai_review_summary[:200]}"

        current_key = os.path.splitext(file_name)[0]
        current_author = author_map.get(current_key) or author_map.get(file_name)
        if current_author:
            notified_authors.add(current_author)

        notify_results = []
        if notified_authors:
            try:
                from Implement.hotfixImpl.c7KimRobot import C7KimRobot
                kim_robot = C7KimRobot()
                for author_username in sorted(notified_authors):
                    success, err = kim_robot.send_msg_to_user(author_username, msg_body)
                    notify_results.append({
                        'username': author_username,
                        'success': success,
                        'error': err if not success else ''
                    })
            except Exception as e:
                app.logger.error(f"notifyHotfixConflict: Kim notify failed: {e}")
                return jsonify({
                    'code': 1,
                    'message': f'Conflict detected but Kim notification failed: {str(e)}',
                    'conflicts': formatted_conflicts,
                    'notifiedAuthors': list(notified_authors),
                    'notifyResults': []
                })

        return jsonify({
            'code': 0,
            'message': f'Notified {len(notified_authors)} authors about conflicts',
            'conflicts': formatted_conflicts,
            'notifiedAuthors': list(sorted(notified_authors)),
            'notifyResults': notify_results
        })
    except Exception as e:
        app.logger.error(f"_check_single_file_conflicts_with_author: error: {e}")
        return jsonify({'code': -1, 'errMsg': str(e)}), 500


# ── Hotfix 目录定时监控接口 ──────────────────────────────────

@app.route('/hotfixDirWatchState', methods=['GET'])
def hotfixDirWatchState():
    """
    查看 hotfix 目录监控状态
    
    返回：
    - changelists: 各 side 当前记录的 changelist 号
    - updated_at: 最近一次状态更新时间
    - notified_conflicts_count: 已通知冲突记录数量
    - notified_conflicts: 所有已通知冲突详情
    - is_checking: 当前是否有检查任务正在运行
    """
    from Implement.hotfixImpl.hotfixDirWatcher import (
        _load_state, _load_notified_conflicts, _is_check_running, _STATE_FILE, _get_mongo
    )
    import os as _os

    state = _load_state()
    notified = _load_notified_conflicts()

    result = {
        'code': 0,
        'changelists': state,
        'notified_conflicts_count': len(notified),
        'notified_conflicts': notified,
        'is_checking': _is_check_running(),
    }

    # 优先从 MongoDB 读取 updated_at
    try:
        mongo = _get_mongo()
        if mongo is not None:
            updated_at = mongo.get_state_updated_at()
            if updated_at:
                result['updated_at'] = updated_at
    except Exception:
        pass

    # 降级：从 JSON 文件读取 updated_at
    if 'updated_at' not in result and _os.path.exists(_STATE_FILE):
        try:
            with open(_STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            result['updated_at'] = data.get('updated_at', '')
        except Exception:
            pass

    return jsonify(result)


@app.route('/triggerHotfixDirCheck', methods=['POST'])
def triggerHotfixDirCheck():
    """
    手动触发一次 hotfix 目录检查
    
    请求参数：
    {
        "force": false  // 是否强制重建索引（忽略 changelist 比较）
    }
    """
    from Implement.hotfixImpl.hotfixDirWatcher import check_hotfix_dirs_tick
    
    data = request.get_json() or {}
    force = data.get('force', False)
    
    if force:
        # 强制重建：清除 MongoDB 和 JSON 文件中的 changelist 记录
        from Implement.hotfixImpl.hotfixDirWatcher import _STATE_FILE, _get_mongo
        import os as _os
        # 清 MongoDB state
        try:
            mongo = _get_mongo()
            if mongo is not None:
                mongo.state_col.delete_many({})
                app.logger.info("triggerHotfixDirCheck: cleared MongoDB state for force rebuild")
        except Exception as e:
            app.logger.warning(f"triggerHotfixDirCheck: clear mongo state failed: {e}")
        # 清 JSON 文件
        if _os.path.exists(_STATE_FILE):
            try:
                _os.remove(_STATE_FILE)
                app.logger.info("triggerHotfixDirCheck: removed state file for force rebuild")
            except Exception as e:
                app.logger.warning(f"triggerHotfixDirCheck: remove state file failed: {e}")
    
    try:
        # 在 app context 中执行
        check_hotfix_dirs_tick()
        return jsonify({'code': 0, 'message': 'Check triggered successfully'})
    except Exception as e:
        app.logger.error(f"triggerHotfixDirCheck failed: {e}")
        return jsonify({'code': -1, 'errMsg': str(e)}), 500


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Hotfix 外放顺序管理 API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route('/getHotfixDeployOrder', methods=['GET'])
def getHotfixDeployOrder():
    """
    获取 hotfix 外放顺序规则配置
    
    参数:
        env: 环境 (prod/test)
        branchType: 分支类型 (weekly)
    
    返回:
        {
            "code": 0,
            "rules": [
                {
                    "id": "rule_xxx",
                    "items": [
                        {"fileName": "xxx.lua", "hotfixType": "server"},
                        {"fileName": "yyy.lua", "hotfixType": "server"}
                    ]
                },
                ...
            ]
        }
    """
    try:
        env = request.args.get('env', 'prod')
        branch_type = request.args.get('branchType', 'weekly')
        
        app.logger.info(f"🟡 [加载规则] env={env}, branchType={branch_type}")
        
        from dbImp import redisImp
        redis_key = f"hotfix_deploy_order:{env}:{branch_type}"
        
        rules_json = redisImp.my_redis.get(redis_key)
        if rules_json:
            rules = json.loads(rules_json)
            app.logger.info(f"🟡 [加载规则] 从Redis加载了 {len(rules)} 条规则")
            app.logger.info(f"🟡 [加载规则] 规则内容: {json.dumps(rules, ensure_ascii=False)}")
        else:
            rules = []
            app.logger.info(f"🟡 [加载规则] Redis中没有数据，返回空数组")
        
        return jsonify({'code': 0, 'rules': rules})
    except Exception as e:
        app.logger.error(f"🔴 [加载规则] 加载失败: {e}")
        return jsonify({'code': -1, 'errMsg': str(e)}), 500



@app.route('/saveHotfixDeployOrder', methods=['POST'])
def saveHotfixDeployOrder():
    """
    保存 hotfix 外放顺序规则配置
    
    请求体:
        {
            "env": "prod",
            "branchType": "weekly",
            "rules": [
                {
                    "id": "rule_xxx",
                    "items": [
                        {"fileName": "xxx.lua", "hotfixType": "server"},
                        {"fileName": "yyy.lua", "hotfixType": "server"}
                    ]
                },
                ...
            ]
        }
    
    返回:
        {"code": 0, "message": "saved"}
    """
    try:
        data = request.get_json() or {}
        env = data.get('env', 'prod')
        branch_type = data.get('branchType', 'weekly')
        rules = data.get('rules', [])
        
        app.logger.info(f"🟢 [保存规则] env={env}, branchType={branch_type}, 规则数量={len(rules)}")
        app.logger.info(f"🟢 [保存规则] 规则内容: {json.dumps(rules, ensure_ascii=False)}")
        
        from dbImp import redisImp
        redis_key = f"hotfix_deploy_order:{env}:{branch_type}"
        
        # 保存到 Redis (永久存储，无过期时间)
        rules_json = json.dumps(rules)
        redisImp.my_redis.set(redis_key, rules_json)
        
        # 验证保存
        saved_data = redisImp.my_redis.get(redis_key)
        if saved_data:
            saved_rules = json.loads(saved_data)
            app.logger.info(f"🟢 [保存规则] 验证成功，Redis中保存了 {len(saved_rules)} 条规则")
        else:
            app.logger.warning(f"🔴 [保存规则] 验证失败，Redis中未找到数据！")
        
        app.logger.info(f"saveHotfixDeployOrder: saved {len(rules)} rules for {env}/{branch_type}")
        return jsonify({'code': 0, 'message': 'Deploy order rules saved successfully'})
    except Exception as e:
        app.logger.error(f"🔴 [保存规则] 保存失败: {e}")
        return jsonify({'code': -1, 'errMsg': str(e)}), 500


@app.route('/checkHotfixDeployOrder', methods=['POST'])
def checkHotfixDeployOrder():
    """
    检查 hotfix 外放顺序是否符合规则（支持顺序链）
    
    请求体:
        {
            "env": "prod",
            "branchType": "weekly",
            "fileName": "xxx.lua",
            "hotfixType": "server",
            "effectTargets": ["server1", "server2"] 或 ["tag1"],
            "effectMode": "servers" 或 "tags"
        }
    
    返回:
        {
            "code": 0,
            "pass": true/false,
            "warning": "警告信息" (如果有),
            "violatedRules": ["规则1", "规则2", ...],
            "currentStatus": "当前状态"
        }
    """
    try:
        data = request.get_json() or {}
        env = data.get('env', 'prod')
        branch_type = data.get('branchType', 'weekly')
        file_name = data.get('fileName', '')
        hotfix_type = data.get('hotfixType', '')
        
        from dbImp import redisImp
        redis_key = f"hotfix_deploy_order:{env}:{branch_type}"
        
        # 读取配置的规则
        rules_json = redisImp.my_redis.get(redis_key)
        if not rules_json:
            # 没有配置规则，直接通过
            return jsonify({'code': 0, 'pass': True})
        
        rules = json.loads(rules_json)
        if not rules:
            return jsonify({'code': 0, 'pass': True})
        
        # 查找包含当前文件的规则
        relevant_rules = []
        for rule in rules:
            items = rule.get('items', [])
            # 检查当前文件是否在规则链中
            file_positions = []
            for i, item in enumerate(items):
                if item.get('fileName') == file_name and item.get('hotfixType') == hotfix_type:
                    file_positions.append(i)
            
            # 如果当前文件在规则链中（且不是第一个），则需要检查
            for pos in file_positions:
                if pos > 0:
                    relevant_rules.append({
                        'rule': rule,
                        'position': pos,
                        'items': items
                    })
        
        if not relevant_rules:
            # 当前文件不在任何规则链中，或都是第一个位置，直接通过
            return jsonify({'code': 0, 'pass': True})
        
        # 检查每条相关规则的前置条件
        violated_rules = []
        missing_files = []
        
        for relevant in relevant_rules:
            items = relevant['items']
            position = relevant['position']
            
            # 检查所有前置文件（position之前的所有文件）
            for i in range(position):
                predecessor = items[i]
                pred_file = predecessor.get('fileName')
                pred_type = predecessor.get('hotfixType')
                
                # 读取对应类型的manifest
                manifest_p4_path = f"//C7/Development/Weekly/Server/hotfix/{pred_type}_hotfix/{'manifest_ci_use__.json' if env == 'test' else 'manifest.json'}"
                
                try:
                    file_ret = p4Imp.getFileContent(manifest_p4_path)
                    if file_ret.get('code') == 0:
                        manifest_content = file_ret.get('content', '')
                        manifest_data = json.loads(manifest_content) if manifest_content else []
                    else:
                        manifest_data = []
                except:
                    manifest_data = []
                
                # 检查前置文件是否在manifest中
                found = False
                for manifest_record in manifest_data:
                    if manifest_record.get('FileName') == pred_file:
                        found = True
                        break
                
                if not found:
                    # 构建规则描述（显示完整链）
                    type_name_map = {'server': '服务端', 'client': '客户端', 'crates': 'Cpp'}
                    chain_parts = []
                    for item in items:
                        item_type_name = type_name_map.get(item['hotfixType'], item['hotfixType'])
                        chain_parts.append(f"[{item_type_name}] {item['fileName']}")
                    
                    rule_desc = ' → '.join(chain_parts)
                    
                    if rule_desc not in violated_rules:
                        violated_rules.append(rule_desc)
                    
                    pred_type_name = type_name_map.get(pred_type, pred_type)
                    missing_file_desc = f"[{pred_type_name}] {pred_file}"
                    if missing_file_desc not in missing_files:
                        missing_files.append(missing_file_desc)
        
        if violated_rules:
            current_status_str = f"尝试外放 {file_name}，但以下前置文件尚未外放：{', '.join(missing_files)}"
            
            return jsonify({
                'code': 0,
                'pass': False,
                'warning': f"检测到外放顺序异常！违反了 {len(violated_rules)} 条规则",
                'violatedRules': violated_rules,
                'currentStatus': current_status_str
            })
        
        return jsonify({'code': 0, 'pass': True})
        
    except Exception as e:
        app.logger.error(f"checkHotfixDeployOrder failed: {e}")
        return jsonify({'code': -1, 'errMsg': str(e)}), 500


# region Jenkins 接口

@app.route('/triggerJenkinsReloadServer', methods=['POST'])
def triggerJenkinsReloadServer():
    """
    触发 Jenkins Reload Server Job
    
    请求体：
    {
        "projectCode": "C7",
        "changelistId": "12345678",
        "namespaces": ["namespace1", "namespace2"] 或 "namespace1",  // 命名空间列表
        "groups": ["group1", "group2"] 或 "group1",                 // 组列表（仅IDC环境）
        "hotfixTypes": ["lua", "excel", "crates"],                  // Hotfix类型列表
        "deployMode": "namespace" | "group"                         // 部署模式（仅IDC环境）
    }
    
    返回：
    {
        "code": 0,
        "success": true,
        "env": "staging" | "idc",
        "message": "成功触发 内部(Staging) Jenkins Job",
        "jenkinsUrl": "http://..."
    }
    """
    from Implement.hotfixImpl.jenkinsImp import JenkinsClient
    
    data = request.get_json() or {}
    project_code = data.get('projectCode', 'C7')
    changelist_id = data.get('changelistId')
    namespaces = data.get('namespaces', [])
    groups = data.get('groups', [])
    hotfix_types = data.get('hotfixTypes', [])
    deploy_mode = data.get('deployMode')
    
    # 记录请求参数日志
    app.logger.info(f"[Jenkins Trigger] Request received - changelist: {changelist_id}, "
                   f"namespaces: {namespaces}, groups: {groups}, "
                   f"hotfixTypes: {hotfix_types}, deployMode: {deploy_mode}")
    
    # 兼容旧接口的 namespace 参数
    if not namespaces and 'namespace' in data:
        namespaces = data.get('namespace')
        app.logger.info(f"[Jenkins Trigger] Using legacy 'namespace' parameter: {namespaces}")
    
    if not changelist_id:
        app.logger.warning("[Jenkins Trigger] Missing changelistId parameter")
        return jsonify({'code': -1, 'success': False, 'errMsg': 'Missing changelistId'}), 400
    
    if not namespaces and not groups:
        app.logger.warning("[Jenkins Trigger] Missing both namespaces and groups parameters")
        return jsonify({'code': -1, 'success': False, 'errMsg': 'Missing namespaces or groups'}), 400
    
    try:
        app.logger.info(f"[Jenkins Trigger] Creating Jenkins client for project: {project_code}")
        jenkins_client = JenkinsClient(logger=app.logger)
        
        app.logger.info(f"[Jenkins Trigger] Calling trigger_reload_server with params: "
                       f"changelist={changelist_id}, namespaces={namespaces}, "
                       f"groups={groups}, hotfix_types={hotfix_types}, deploy_mode={deploy_mode}")
        
        result = jenkins_client.trigger_reload_server(
            project_code=project_code,
            changelist_id=changelist_id,
            namespaces=namespaces,
            groups=groups,
            hotfix_types=hotfix_types,
            deploy_mode=deploy_mode
        )
        
        if result['success']:
            app.logger.info(f"[Jenkins Trigger] SUCCESS - env: {result['env']}, "
                          f"message: {result['message']}, url: {result['jenkins_url']}")
            return jsonify({
                'code': 0,
                'success': True,
                'env': result['env'],
                'message': result['message'],
                'jenkinsUrl': result['jenkins_url']
            })
        else:
            app.logger.error(f"[Jenkins Trigger] FAILED - env: {result['env']}, "
                           f"message: {result['message']}")
            return jsonify({
                'code': -1,
                'success': False,
                'env': result['env'],
                'errMsg': result['message']
            }), 500
    except Exception as e:
        app.logger.error(f"[Jenkins Trigger] Exception occurred: {str(e)}", exc_info=True)
        return jsonify({'code': -1, 'success': False, 'errMsg': str(e)}), 500


# endregion
