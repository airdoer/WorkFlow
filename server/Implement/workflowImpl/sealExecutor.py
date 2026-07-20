"""
Seal (海豹) 节点执行器 — 通过 SOPS (SRE OPS) 开放 API 创建并启动部署任务。

功能：
1. 从 c7Server.json 获取目标服务器的 tree_id
2. 从 c7ServerTags.json 展开服务器分组
3. 从 c7SealOperation.json 获取流程配置（template_id, source, args）
4. 调用 SOPS API 创建并启动任务
5. 返回 _sealPolling 标记，由 WorkflowRuntime 启动后台轮询等待任务完成

执行分两个阶段：
  Phase 1（同步）: 创建+启动任务 → 返回创建结果（createSuccess, taskId, taskUrl）
  Phase 2（异步）: 后台线程每 60s 轮询 SOPS 状态 → 最多 30 次 → 推送最终结果（executionSuccess）

参考: e:\Code\gitlab\c7-server-depoly\seal.py
"""
import logging

import requests
from Implement.hotfixImpl.sealImp import SealClient, SOPS_TOKEN
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)

# ── 全局 SealClient 单例（供路由层调用） ────────────────────────────────────
_seal_client = SealClient(logger_override=logger)


def load_seal_operation_options() -> list:
    """路由层入口：返回 Seal 操作选项列表"""
    return _seal_client.load_seal_operation_options()


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
        - serverName: 目标服务器 namespace 或分组 key（必填，自动在 Tags/Servers 中查找）
        - operation: 流程名，如 "Deploy", "StartProd"（必填）
        - executor: 执行人（默认 chenzhixu）
        """
        client = _seal_client

        # 获取参数：连线传入的值（input_data）优先，config 手动值作为 fallback
        server_name = input_data.get('serverName', '') or config.get('serverName', '')
        operation = config.get('operation', '')
        executor = config.get('executor', 'chenzhixu') or 'chenzhixu'

        if not server_name:
            return {"error": "serverName 不能为空（请选择目标服务器或分组）"}
        if not operation:
            return {"error": "operation 不能为空（请选择流程）"}

        # 检查 SOPS 环境变量
        if not SOPS_TOKEN:
            return {"error": "SOPS_TOKEN 环境变量未设置"}

        # 解析目标环境（自动在 Tags 和 Servers 中查找 tree_id）
        target_envs = server_name.split(',') if ',' in server_name else [server_name]
        try:
            host_ids = client.resolve_host_ids(target_envs)
        except ValueError as e:
            return {"error": str(e)}

        # 加载流程配置
        ops = client.load_seal_operations()
        if operation not in ops:
            return {"error": f"流程 '{operation}' 不存在（c7SealOperation.json 中未定义）"}

        op_info = ops[operation]
        template_id = op_info.get('template_id')
        source_file = op_info.get('source', '')
        script_args = op_info.get('args', '')
        args_def = op_info.get('args_def', [])

        # 从 config 和 input_data 中收集 args_def 定义的动态参数
        # 连线传入的值（input_data）优先；config 是手动填写值作为 fallback
        extra_args = {}
        for arg_def in args_def:
            arg_key = arg_def.get('key', '')
            arg_val = input_data.get(arg_key, '') or config.get(arg_key, '')
            if arg_val:
                extra_args[arg_key] = arg_val

        # 特殊处理：source_file 用于替换 SOPS constants 中的 ${source_file}
        if extra_args.get('source_file'):
            source_file = extra_args['source_file']

        if not template_id:
            return {"error": f"流程 '{operation}' 缺少 template_id"}

        # 构建任务名
        task_name_prefix = f"C7_{operation}_" + "+".join(target_envs)

        # 构建额外 constants（去掉已用于 source_file 替换的参数）
        sops_extra_args = {k: v for k, v in extra_args.items() if k != 'source_file'}

        # 创建任务
        try:
            create_resp = client.create_task(template_id, host_ids, source_file,
                                             script_args, task_name_prefix,
                                             extra_args=sops_extra_args)
        except requests.exceptions.RequestException as e:
            client._log_exception("[Seal] Create task request failed: %s", e)
            return {"error": f"创建任务请求失败: {e}"}

        if not create_resp.get("result"):
            error_msg = create_resp.get("message", str(create_resp))
            client._log_error("[Seal] Create task failed: %s", create_resp)
            return {"error": f"创建任务失败: {error_msg}"}

        task_id = create_resp.get("data", {}).get("task_id")

        # 启动任务
        try:
            start_resp = client.start_task(task_id, executor)
        except requests.exceptions.RequestException as e:
            client._log_exception("[Seal] Start task request failed: %s", e)
            return {
                "error": f"启动任务请求失败: {e}",
                "taskId": task_id,
                "createSuccess": False,
            }

        if not start_resp.get("result"):
            error_msg = start_resp.get("message", str(start_resp))
            client._log_error("[Seal] Start task failed: %s", start_resp)
            return {
                "error": f"启动任务失败: {error_msg}",
                "taskId": task_id,
                "createSuccess": False,
            }

        task_url = start_resp.get("data", {}).get("task_url", "")
        client._log_info("[Seal] Task started: id=%s, url=%s", task_id, task_url)

        # Phase 1 完成：任务已创建并启动
        # Phase 2（后台轮询）由 WorkflowRuntime 根据 _sealPolling 标记启动
        return {
            "__runtime_type__": "object",
            "__value__": None,
            "createSuccess": True,
            "taskId": task_id,
            "taskUrl": task_url,
            "task_id": task_id,
            "task_url": task_url,
            "operation": operation,
            "target_envs": target_envs,
            "host_ids": host_ids,
            "template_id": template_id,
            # ── 异步轮询标记（WorkflowRuntime 识别） ──
            "_sealPolling": True,
            "_sealTaskId": task_id,
        }
