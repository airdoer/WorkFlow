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
                'args_def': info.get('args_def', []),
                'seal_env': info.get('seal_env', ''),
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

    def get_task_detail(self, task_id: str) -> dict:
        """
        查询任务详情（包含任务名、执行人、失败节点等）。

        API 返回示例:
        {
            "result": true,
            "data": {
                "instance_id": "n7ab8a...",
                "name": "C7_DeployTest_test_c7",
                "executor": "chenzhixu",
                "state": "FINISHED",
                "task_url": "https://...",
                "failed_nodes": null
            },
            "code": 0,
            "message": ""
        }
        """
        api = f"{SOPS_HOST}/api/open/taskflow/{task_id}/detail"
        headers = self._get_headers()
        resp = requests.get(api, headers=headers, timeout=30)
        return resp.json()

    def wait_for_task_completion(self, task_id: str,
                                  poll_interval: float = 10.0,
                                  timeout: float = 1800.0,
                                  terminal_states: tuple = None) -> dict:
        """
        轮询等待任务执行完成。

        参数:
            task_id: SOPS 任务 ID
            poll_interval: 轮询间隔（秒），默认 10s
            timeout: 超时时间（秒），默认 1800s（30 分钟）
            terminal_states: 视为"已完成"的终态列表，默认
                ('FINISHED', 'FAILED', 'REVOKED', 'SUSPENDED')

        返回:
            dict 包含:
            - completed (bool): 是否到达终态
            - state (str): 最终状态
            - elapsed (float): 等待耗时（秒）
            - poll_count (int): 轮询次数
            - last_status (dict): 最后一次 API 返回的完整状态
            - error (str): 错误信息（如有）
            - timeout (bool): 是否超时

        SOPS 任务状态参考:
            CREATED   - 已创建（未启动）
            RUNNING   - 执行中
            SUSPENDED - 暂停/等待审批
            FINISHED  - 执行成功
            FAILED    - 执行失败
            REVOKED   - 已撤销
        """
        if terminal_states is None:
            terminal_states = ('FINISHED', 'FAILED', 'REVOKED', 'SUSPENDED')

        start_time = time.time()
        poll_count = 0
        last_status = {}

        self._log_info("[Seal] Waiting for task %s to complete (timeout=%ds, interval=%ds)",
                       task_id, timeout, poll_interval)

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                self._log_warning("[Seal] Task %s wait timed out after %.1fs (%d polls)",
                                  task_id, elapsed, poll_count)
                return {
                    "completed": False,
                    "state": last_status.get("data", {}).get("state", "UNKNOWN"),
                    "elapsed": elapsed,
                    "poll_count": poll_count,
                    "last_status": last_status,
                    "error": "等待超时",
                    "timeout": True,
                }

            try:
                status_resp = self.get_task_status(task_id)
            except requests.exceptions.RequestException as e:
                self._log_warning("[Seal] Task %s status poll failed: %s (will retry)", task_id, e)
                time.sleep(poll_interval)
                poll_count += 1
                continue

            last_status = status_resp
            poll_count += 1

            if not status_resp.get("result", False):
                self._log_warning("[Seal] Task %s status API error: %s", task_id, status_resp)
                time.sleep(poll_interval)
                continue

            # 从响应 data 中提取 state
            data = status_resp.get("data", {})
            state = data.get("state", "")

            self._log_info("[Seal] Task %s state=%s (%.1fs elapsed, poll #%d)",
                           task_id, state, elapsed, poll_count)

            if state.upper() in terminal_states:
                self._log_info("[Seal] Task %s reached terminal state: %s (%.1fs)",
                               task_id, state, elapsed)

                # 任务到达终态时，额外获取详情（含执行人、任务名、失败节点）
                detail = {}
                try:
                    detail_resp = self.get_task_detail(task_id)
                    if detail_resp.get("result"):
                        detail = detail_resp.get("data", {})
                except Exception:
                    pass  # detail 获取失败不影响主流程

                is_success = state.upper() == "FINISHED"
                failed_nodes = detail.get("failed_nodes")

                return {
                    "completed": True,
                    "state": state,
                    "elapsed": elapsed,
                    "poll_count": poll_count,
                    "last_status": status_resp,
                    "detail": detail,
                    "failed_nodes": failed_nodes,
                    "error": "" if is_success and not failed_nodes
                             else (f"失败节点: {failed_nodes}" if failed_nodes
                                   else f"任务终态: {state}"),
                    "timeout": False,
                }

            time.sleep(poll_interval)
