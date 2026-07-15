"""
Seal (海豹) 节点执行器 — 通过 SOPS (SRE OPS) 开放 API 创建并启动部署任务。

功能：
1. 从 c7Server.json 获取目标服务器的 tree_id
2. 从 c7ServerTags.json 展开服务器分组
3. 从 c7SealOperation.json 获取流程配置（template_id, source, args）
4. 调用 SOPS API 创建并启动任务

参考: e:\Code\gitlab\c7-server-depoly\seal.py
"""
import json
import logging
import os
import time
import uuid

import requests
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)

# ── SOPS 配置 ────────────────────────────────────────────────────────────────
SOPS_HOST = "https://sre-sops.corp.kuaishou.com"
SOPS_TOKEN = os.getenv("SOPS_TOKEN", "")
SOPS_PROJECT = os.getenv("SOPS_PROJECT", "")

# ── 数据文件缓存 ────────────────────────────────────────────────────────────
_data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'C7')

_seal_cache: dict = {}
_seal_cache_time: float = 0
_CACHE_TTL = 300  # 5分钟缓存


def _load_json(filename: str) -> dict:
    path = os.path.join(_data_dir, filename)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning("[Seal] Failed to load %s: %s", filename, e)
        return {}


def _load_seal_operations() -> dict:
    """加载 c7SealOperation.json 流程定义"""
    return _load_json('c7SealOperation.json')


def _resolve_host_ids(target_envs: list, target_env_mode: str) -> list:
    """
    将目标环境列表解析为 host_id 列表。
    - namespace 模式：每个 target_env 直接查 tree_id
    - group 模式：先从 c7ServerTags.json 展开分组，再查 tree_id
    """
    servers = _load_json('c7Server.json')
    tags = _load_json('c7ServerTags.json')

    resolved_envs = []
    if target_env_mode == 'group':
        for group_key in target_envs:
            if group_key not in tags:
                raise ValueError(f"分组 '{group_key}' 不存在（c7ServerTags.json 中未定义）")
            namespaces = tags[group_key].get('namespaces', [])
            resolved_envs.extend(namespaces)
    else:
        resolved_envs = target_envs

    host_ids = []
    for env in resolved_envs:
        if env not in servers:
            raise ValueError(f"服务器 '{env}' 不存在（c7Server.json 中未定义）")
        tree_id = servers[env].get('tree_id')
        if not tree_id:
            raise ValueError(f"服务器 '{env}' 没有 tree_id（无法通过 Seal 部署）")
        host_ids.append(tree_id)

    return host_ids


def load_seal_operation_options() -> list:
    """
    返回 Seal 操作选项列表，供前端下拉框使用。
    格式: [{ label, value, template_id, description }]
    """
    now = time.time()
    if _seal_cache and (now - _seal_cache_time) < _CACHE_TTL:
        return _seal_cache.get('options', [])

    ops = _load_seal_operations()
    options = []
    for key, info in ops.items():
        options.append({
            'label': info.get('label', key),
            'value': key,
            'template_id': info.get('template_id'),
            'description': info.get('description', ''),
        })

    _seal_cache['options'] = options
    _seal_cache_time = now
    return options


def _get_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SOPS_TOKEN}",
        "Project": f"{SOPS_PROJECT}",
        "Request-Id": uuid.uuid4().hex,
    }


def _build_request_body(template_id: int, host_ids: list, source_file: str,
                         script_args: str, task_name: str,
                         exclude_task_nodes_id: list = None,
                         extra_args: dict = None) -> str:
    """构建 SOPS 创建任务请求体"""
    if exclude_task_nodes_id is None:
        exclude_task_nodes_id = []
    if extra_args is None:
        extra_args = {}

    host_id_array = [{"id": hid} for hid in host_ids]
    constants = {
        "${servers}": {
            "static_ip_table_config": [],
            "selectors": ["topo"],
            "ip": {"nodes": [], "instances": []},
            "topo": host_id_array,
            "group": [],
            "filters": [],
            "excludes": [],
            "with_cloud_id": False
        },
        "${source_file}": source_file,
        "${script_args}": script_args
    }
    for k, v in extra_args.items():
        constants[f"${{{k}}}"] = v

    body = {
        "task_name": task_name,
        "template": template_id,
        "constants": constants,
        "exclude_task_nodes_id": exclude_task_nodes_id,
    }
    return json.dumps(body)


def _create_task(template_id: int, host_ids: list, source_file: str,
                  script_args: str, task_name: str,
                  exclude_task_nodes_id: list = None,
                  extra_args: dict = None) -> dict:
    """调用 SOPS API 创建任务"""
    api = f"{SOPS_HOST}/api/open/taskflow/create"
    headers = _get_headers()
    body = _build_request_body(template_id, host_ids, source_file,
                               script_args, task_name,
                               exclude_task_nodes_id, extra_args)
    logger.info("[Seal] Creating task: template=%d, hosts=%s, source=%s, name=%s",
                template_id, host_ids, source_file, task_name)
    resp = requests.post(api, headers=headers, data=body, timeout=30)
    return resp.json()


def _start_task(task_id: str, executor: str = "chenzhixu") -> dict:
    """调用 SOPS API 启动已创建的任务"""
    api = f"{SOPS_HOST}/api/open/taskflow/{task_id}/start"
    headers = _get_headers()
    body = json.dumps({"executor": executor})
    logger.info("[Seal] Starting task: id=%s, executor=%s", task_id, executor)
    resp = requests.post(api, headers=headers, data=body, timeout=30)
    return resp.json()


def _get_task_status(task_id: str) -> dict:
    """查询任务状态"""
    api = f"{SOPS_HOST}/api/open/taskflow/{task_id}/status"
    headers = _get_headers()
    resp = requests.get(api, headers=headers, timeout=30)
    return resp.json()


class SealExecutor(BaseNodeExecutor):
    type = "seal"

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        Seal 节点执行：
        1. 从 config 或 input_data 获取 serverName（目标服务器/分组）
        2. 从 config 获取 operation（流程名）
        3. 解析目标环境 → host_ids
        4. 从 c7SealOperation.json 获取 template_id、source、args
        5. 调用 SOPS API 创建并启动任务

        config 字段：
        - serverName: 目标服务器 namespace 或分组 key（必填）
        - targetEnvMode: "namespace" 或 "group"（默认 namespace）
        - operation: 流程名，如 "Deploy", "RestartServer"（必填）
        - executor: 执行人（默认 chenzhixu）
        """
        # 获取参数：config 优先，input_data 次之
        server_name = config.get('serverName', '') or input_data.get('serverName', '')
        target_env_mode = config.get('targetEnvMode', 'namespace') or 'namespace'
        operation = config.get('operation', '')
        executor = config.get('executor', 'chenzhixu') or 'chenzhixu'

        if not server_name:
            return {"success": False, "error": "serverName 不能为空（请选择目标服务器或分组）"}
        if not operation:
            return {"success": False, "error": "operation 不能为空（请选择流程）"}

        # 检查 SOPS 环境变量
        if not SOPS_TOKEN:
            return {"success": False, "error": "SOPS_TOKEN 环境变量未设置"}

        # 解析目标环境
        target_envs = server_name.split(',') if ',' in server_name else [server_name]
        try:
            host_ids = _resolve_host_ids(target_envs, target_env_mode)
        except ValueError as e:
            return {"success": False, "error": str(e)}

        # 加载流程配置
        ops = _load_seal_operations()
        if operation not in ops:
            return {"success": False, "error": f"流程 '{operation}' 不存在（c7SealOperation.json 中未定义）"}

        op_info = ops[operation]
        template_id = op_info.get('template_id')
        source_file = op_info.get('source', '')
        script_args = op_info.get('args', '')

        if not template_id:
            return {"success": False, "error": f"流程 '{operation}' 缺少 template_id"}

        # 构建任务名
        task_name_prefix = f"C7_{operation}_" + "+".join(target_envs)

        # 创建任务
        try:
            create_resp = _create_task(template_id, host_ids, source_file,
                                       script_args, task_name_prefix)
        except requests.exceptions.RequestException as e:
            logger.exception("[Seal] Create task request failed: %s", e)
            return {"success": False, "error": f"创建任务请求失败: {e}"}

        if not create_resp.get("result"):
            error_msg = create_resp.get("message", str(create_resp))
            logger.error("[Seal] Create task failed: %s", create_resp)
            return {"success": False, "error": f"创建任务失败: {error_msg}"}

        task_id = create_resp.get("data", {}).get("task_id")

        # 启动任务
        try:
            start_resp = _start_task(task_id, executor)
        except requests.exceptions.RequestException as e:
            logger.exception("[Seal] Start task request failed: %s", e)
            return {
                "success": False,
                "error": f"启动任务请求失败: {e}",
                "task_id": task_id,
            }

        if not start_resp.get("result"):
            error_msg = start_resp.get("message", str(start_resp))
            logger.error("[Seal] Start task failed: %s", start_resp)
            return {
                "success": False,
                "error": f"启动任务失败: {error_msg}",
                "task_id": task_id,
            }

        task_url = start_resp.get("data", {}).get("task_url", "")
        logger.info("[Seal] Task started: id=%s, url=%s", task_id, task_url)

        return {
            "success": True,
            "task_id": task_id,
            "task_url": task_url,
            "operation": operation,
            "target_envs": target_envs,
            "host_ids": host_ids,
            "template_id": template_id,
        }
