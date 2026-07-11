import json
import os
import time
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

# 缓存
_c7_cache: dict = {}
_c7_cache_time: dict = {}
_CACHE_TTL = 300  # 5分钟缓存


def _get_cached(key: str):
    now = time.time()
    if key in _c7_cache and (now - _c7_cache_time.get(key, 0)) < _CACHE_TTL:
        return _c7_cache[key]
    return None


def _set_cached(key: str, value):
    _c7_cache[key] = value
    _c7_cache_time[key] = time.time()


def _load_c7_server_list():
    """加载 C7 服务器列表（服务器 + 服务器分组），带缓存"""
    cached = _get_cached('c7_server_options')
    if cached is not None:
        return cached

    data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'C7')
    options = []

    # 加载单个服务器
    server_path = os.path.join(data_dir, 'c7Server.json')
    try:
        with open(server_path, 'r', encoding='utf-8') as f:
            servers = json.load(f)
        for namespace, info in servers.items():
            options.append({
                'label': info.get('name', namespace),
                'value': namespace,
                'type': 'server',
                'namespace': namespace,
                'server_id': info.get('server_id'),
            })
    except Exception as e:
        pass

    # 加载服务器分组
    tags_path = os.path.join(data_dir, 'c7ServerTags.json')
    try:
        with open(tags_path, 'r', encoding='utf-8') as f:
            tags = json.load(f)
        for tag_key, tag_info in tags.items():
            options.append({
                'label': f"[分组] {tag_info.get('name', tag_key)}",
                'value': tag_key,
                'type': 'group',
            })
    except Exception as e:
        pass

    _set_cached('c7_server_options', options)
    return options


class C7ServerExecutor(BaseNodeExecutor):
    type = "c7server"

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        C7Server 节点：从下拉框选择服务器或服务器分组，输出服务器名（namespace 或 tag key）。
        - serverName: 下拉框选中的 namespace 或 tag key（必填）
        """
        server_name = config.get('serverName', '')
        if not server_name:
            raise ValueError("serverName 不能为空")
        return {'serverName': str(server_name)}
