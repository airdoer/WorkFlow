# -*- coding: utf-8 -*-
"""
Seal (海豹) 客户端封装
通过 SOPS (SRE OPS) 开放 API 创建并启动部署任务
"""

import json
import logging
import os
import time
import uuid

import requests

logger = logging.getLogger(__name__)

# ── SOPS 配置 ────────────────────────────────────────────────────────────────
SOPS_HOST = "https://sre-sops.corp.kuaishou.com"
SOPS_TOKEN = os.getenv("SOPS_TOKEN", "")
SOPS_PROJECT = os.getenv("SOPS_PROJECT", "")

# ── 数据文件目录 ────────────────────────────────────────────────────────────
_data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'C7')


class SealClient:
    """Seal (SOPS) 客户端类，用于创建并启动部署任务"""

    def __init__(self, logger_override=None):
        self.logger = logger_override or logger
        self._cache: dict = {}
        self._cache_time: float = 0
        self._CACHE_TTL = 300  # 5分钟缓存

    # ── 日志辅助 ─────────────────────────────────────────────────────────────

    def _log_info(self, msg, *args):
        self.logger.info(msg, *args)

    def _log_warning(self, msg, *args):
        self.logger.warning(msg, *args)

    def _log_error(self, msg, *args):
        self.logger.error(msg, *args)

    def _log_exception(self, msg, *args):
        self.logger.exception(msg, *args)

    # ── 数据文件加载 ────────────────────────────────────────────────────────

    def _load_json(self, filename: str) -> dict:
        path = os.path.join(_data_dir, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self._log_warning("[Seal] Failed to load %s: %s", filename, e)
            return {}

    def load_seal_operations(self) -> dict:
        """加载 c7SealOperation.json 流程定义"""
        return self._load_json('c7SealOperation.json')

    def load_seal_operation_options(self) -> list:
        """
        返回 Seal 操作选项列表，供前端下拉框使用。
        格式: [{ label, value, template_id, description }]
        """
        now = time.time()
        if self._cache and (now - self._cache_time) < self._CACHE_TTL:
            return self._cache.get('options', [])

        ops = self.load_seal_operations()
        options = []
        for key, info in ops.items():
            options.append({
                'label': info.get('label', key),
                'value': key,
                'template_id': info.get('template_id'),
                'description': info.get('description', ''),
            })

        self._cache['options'] = options
        self._cache_time = now
        return options

    # ── 目标环境解析 ────────────────────────────────────────────────────────

    def resolve_host_ids(self, target_envs: list) -> list:
        """
        将目标环境列表解析为 host_id 列表。
        查找优先级：
        1. 先在 c7ServerTags.json 中查找，如果分组有 tree_id 则直接使用分组的 tree_id
        2. 如果分组没有 tree_id，则展开为 namespaces 再逐个查 c7Server.json
        3. 如果不在 Tags 中，直接在 c7Server.json 中查找（namespace 模式）
        """
        servers = self._load_json('c7Server.json')
        tags = self._load_json('c7ServerTags.json')

        host_ids = []
        for env_key in target_envs:
            # 优先在 Tags 中查找
            if env_key in tags:
                tag_info = tags[env_key]
                tag_tree_id = tag_info.get('tree_id')
                if tag_tree_id:
                    # 分组有 tree_id，直接使用（如 online → 99522）
                    host_ids.append(tag_tree_id)
                    continue
                # 分组没有 tree_id，展开为 namespaces 再逐个查
                namespaces = tag_info.get('namespaces', [])
                for ns in namespaces:
                    if ns not in servers:
                        raise ValueError(f"服务器 '{ns}' 不存在（c7Server.json 中未定义）")
                    tree_id = servers[ns].get('tree_id')
                    if not tree_id:
                        raise ValueError(f"服务器 '{ns}' 没有 tree_id（无法通过 Seal 部署）")
                    host_ids.append(tree_id)
            elif env_key in servers:
                # 直接是 namespace，查 c7Server.json
                tree_id = servers[env_key].get('tree_id')
                if not tree_id:
                    raise ValueError(f"服务器 '{env_key}' 没有 tree_id（无法通过 Seal 部署）")
                host_ids.append(tree_id)
            else:
                raise ValueError(f"'{env_key}' 在 c7Server.json 和 c7ServerTags.json 中均未定义")

        return host_ids

    # ── SOPS HTTP 请求 ──────────────────────────────────────────────────────

    @staticmethod
    def _get_headers() -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SOPS_TOKEN}",
            "Project": f"{SOPS_PROJECT}",
            "Request-Id": uuid.uuid4().hex,
        }

    def _build_request_body(self, template_id: int, host_ids: list, source_file: str,
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

    def create_task(self, template_id: int, host_ids: list, source_file: str,
                    script_args: str, task_name: str,
                    exclude_task_nodes_id: list = None,
                    extra_args: dict = None) -> dict:
        """调用 SOPS API 创建任务"""
        api = f"{SOPS_HOST}/api/open/taskflow/create"
        headers = self._get_headers()
        body = self._build_request_body(template_id, host_ids, source_file,
                                        script_args, task_name,
                                        exclude_task_nodes_id, extra_args)
        self._log_info("[Seal] Creating task: template=%d, hosts=%s, source=%s, name=%s",
                       template_id, host_ids, source_file, task_name)
        resp = requests.post(api, headers=headers, data=body, timeout=30)
        return resp.json()

    def start_task(self, task_id: str, executor: str = "chenzhixu") -> dict:
        """调用 SOPS API 启动已创建的任务"""
        api = f"{SOPS_HOST}/api/open/taskflow/{task_id}/start"
        headers = self._get_headers()
        body = json.dumps({"executor": executor})
        self._log_info("[Seal] Starting task: id=%s, executor=%s", task_id, executor)
        resp = requests.post(api, headers=headers, data=body, timeout=30)
        return resp.json()

    def get_task_status(self, task_id: str) -> dict:
        """查询任务状态"""
        api = f"{SOPS_HOST}/api/open/taskflow/{task_id}/status"
        headers = self._get_headers()
        resp = requests.get(api, headers=headers, timeout=30)
        return resp.json()
