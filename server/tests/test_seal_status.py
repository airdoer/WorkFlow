# -*- coding: utf-8 -*-
"""
海豹 (Seal) 任务状态查询与等待完成 测试脚本

用法:
    # 1. 先设置环境变量
    set SOPS_TOKEN=你的SOPS_TOKEN
    set SOPS_PROJECT=你的SOPS_PROJECT

    # 2. 测试已有任务的状态查询（用户给出的 instance_id）
    python -m tests.test_seal_status query 5273667

    # 3. 等待任务完成（轮询模式）
    python -m tests.test_seal_status wait 5273667

    # 4. 等待任务完成（自定义超时和间隔）
    python -m tests.test_seal_status wait 5273667 --timeout 600 --interval 5

    # 5. 查询任务详情
    python -m tests.test_seal_status detail 5273667

    # 6. 创建并启动一个新任务（DeployTest），然后等待完成
    python -m tests.test_seal_status create DeployTest test_c7 --timeout 600

    # 7. 完整流程测试：创建 → 启动 → 等待完成
    python -m tests.test_seal_status full DeployTest test_c7
"""

import argparse
import json
import os
import sys
import time

# 将 server/ 加入 sys.path，以便直接 import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from Implement.hotfixImpl.sealImp import SealClient, SOPS_TOKEN, SOPS_PROJECT


def _ensure_env():
    """确保必要环境变量已设置"""
    if not SOPS_TOKEN:
        print("[ERROR] SOPS_TOKEN 环境变量未设置！")
        print("  请执行: set SOPS_TOKEN=你的token")
        sys.exit(1)
    if not SOPS_PROJECT:
        print("[ERROR] SOPS_PROJECT 环境变量未设置！")
        print("  请执行: set SOPS_PROJECT=你的project")
        sys.exit(1)
    print(f"[OK] SOPS_TOKEN = {SOPS_TOKEN[:8]}...")
    print(f"[OK] SOPS_PROJECT = {SOPS_PROJECT}")


def _print_separator(title=""):
    """打印分隔线"""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    else:
        print(f"{'='*60}")


def cmd_query(client: SealClient, task_id: str):
    """查询任务状态"""
    _print_separator(f"查询任务状态: task_id={task_id}")
    try:
        resp = client.get_task_status(task_id)
        print(json.dumps(resp, indent=2, ensure_ascii=False))

        # 解析并打印关键信息
        if resp.get("result"):
            data = resp.get("data", {})
            state = data.get("state", "UNKNOWN")
            print(f"\n[结果] 任务状态: {state}")

            # 尝试打印更多详情
            if "children" in data:
                children = data["children"]
                print(f"\n[子节点] 共 {len(children)} 个:")
                for node_id, node_info in children.items():
                    node_state = node_info.get("state", "UNKNOWN")
                    node_name = node_info.get("name", node_id)
                    print(f"  - {node_name} ({node_id}): {node_state}")
        else:
            print(f"\n[错误] API 返回失败: {resp.get('message', '未知错误')}")

    except Exception as e:
        print(f"[异常] 查询失败: {e}")


def cmd_detail(client: SealClient, task_id: str):
    """查询任务详情"""
    _print_separator(f"查询任务详情: task_id={task_id}")
    try:
        resp = client.get_task_detail(task_id)
        print(json.dumps(resp, indent=2, ensure_ascii=False))

        if resp.get("result"):
            data = resp.get("data", {})
            state = data.get("state", "UNKNOWN")
            task_name = data.get("name", "")
            print(f"\n[结果] 任务名: {task_name}, 状态: {state}")
        else:
            print(f"\n[错误] API 返回失败: {resp.get('message', '未知错误')}")

    except Exception as e:
        print(f"[异常] 查询失败: {e}")


def cmd_wait(client: SealClient, task_id: str, timeout: float, interval: float):
    """等待任务完成"""
    _print_separator(f"等待任务完成: task_id={task_id}")
    print(f"  超时: {timeout}s, 轮询间隔: {interval}s")
    print(f"  开始时间: {time.strftime('%H:%M:%S')}")

    try:
        result = client.wait_for_task_completion(
            task_id, poll_interval=interval, timeout=timeout
        )
        print(f"\n[等待结果]")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        if result["completed"]:
            state = result["state"]
            detail = result.get("detail", {})
            failed_nodes = result.get("failed_nodes")
            task_name = detail.get("name", "")
            executor = detail.get("executor", "")

            if state.upper() == "FINISHED" and not failed_nodes:
                print(f"\n[成功] 任务已完成! 状态={state}, 耗时={result['elapsed']:.1f}s")
                if task_name:
                    print(f"  任务名: {task_name}")
                if executor:
                    print(f"  执行人: {executor}")
            else:
                print(f"\n[警告] 任务到达终态但非成功: 状态={state}, 耗时={result['elapsed']:.1f}s")
                if failed_nodes:
                    print(f"  失败节点: {failed_nodes}")
                print(f"  错误: {result.get('error', '')}")
        else:
            if result.get("timeout"):
                print(f"\n[超时] 等待超过 {timeout}s, 当前状态={result['state']}")
            else:
                print(f"\n[失败] {result.get('error', '未知错误')}")

    except KeyboardInterrupt:
        print(f"\n[中断] 用户手动中断等待")


def cmd_create(client: SealClient, operation: str, server_name: str, timeout: float, interval: float):
    """创建并启动任务，然后等待完成"""
    _print_separator(f"创建并启动任务: operation={operation}, server={server_name}")

    # 1. 解析目标环境
    target_envs = server_name.split(',') if ',' in server_name else [server_name]
    try:
        host_ids = client.resolve_host_ids(target_envs)
        print(f"[OK] 目标环境解析: {target_envs} → host_ids={host_ids}")
    except ValueError as e:
        print(f"[ERROR] 目标环境解析失败: {e}")
        return

    # 2. 加载流程配置
    ops = client.load_seal_operations()
    if operation not in ops:
        print(f"[ERROR] 流程 '{operation}' 不存在")
        print(f"  可用流程: {list(ops.keys())}")
        return

    op_info = ops[operation]
    template_id = op_info.get('template_id')
    source_file = op_info.get('source', '')
    script_args = op_info.get('args', '')

    print(f"[OK] 流程配置: template_id={template_id}, source={source_file}, args={script_args}")

    # 3. 创建任务
    task_name_prefix = f"C7_{operation}_" + "+".join(target_envs)
    try:
        create_resp = client.create_task(template_id, host_ids, source_file,
                                          script_args, task_name_prefix)
    except Exception as e:
        print(f"[ERROR] 创建任务请求失败: {e}")
        return

    print(f"\n[创建响应]")
    print(json.dumps(create_resp, indent=2, ensure_ascii=False))

    if not create_resp.get("result"):
        print(f"[ERROR] 创建任务失败: {create_resp.get('message', '')}")
        return

    task_id = create_resp.get("data", {}).get("task_id")
    print(f"[OK] 任务已创建: task_id={task_id}")

    # 4. 启动任务
    try:
        start_resp = client.start_task(task_id, executor="chenzhixu")
    except Exception as e:
        print(f"[ERROR] 启动任务请求失败: {e}")
        return

    print(f"\n[启动响应]")
    print(json.dumps(start_resp, indent=2, ensure_ascii=False))

    if not start_resp.get("result"):
        print(f"[ERROR] 启动任务失败: {start_resp.get('message', '')}")
        return

    task_url = start_resp.get("data", {}).get("task_url", "")
    print(f"[OK] 任务已启动: task_id={task_id}, url={task_url}")

    # 5. 等待完成
    if timeout > 0:
        cmd_wait(client, task_id, timeout, interval)
    else:
        print(f"\n[跳过等待] 任务已提交, 可通过以下命令查看:")
        print(f"  python -m tests.test_seal_status query {task_id}")
        print(f"  python -m tests.test_seal_status wait {task_id}")
        print(f"\n[任务链接] {task_url}")


def cmd_full(client: SealClient, operation: str, server_name: str):
    """完整流程测试：创建 → 启动 → 轮询等待"""
    cmd_create(client, operation, server_name, timeout=1800, interval=10)


def cmd_probe_apis(client: SealClient, task_id: str):
    """探测所有可能的 SOPS API 端点，找出哪些可用"""
    _print_separator(f"探测 SOPS API 端点: task_id={task_id}")

    import requests

    headers = client._get_headers()

    # 可能的端点列表（基于 BK-SOPS 开放 API 规范）
    possible_endpoints = [
        ("GET", f"/api/open/taskflow/{task_id}/status", "查询任务状态"),
        ("GET", f"/api/open/taskflow/{task_id}/detail", "查询任务详情"),
        ("GET", f"/api/open/taskflow/{task_id}/node_status", "查询节点状态(已确认404)"),
        ("GET", f"/api/open/taskflow/{task_id}/get_task_status", "获取任务状态(旧)"),
        ("GET", f"/api/open/taskflow/{task_id}/get_node_status", "获取节点状态(旧,已确认404)"),
        ("GET", f"/api/open/taskflow/{task_id}/children", "查询子任务"),
        ("GET", f"/api/open/taskflow/{task_id}/data", "查询任务数据"),
        ("GET", f"/api/open/taskflow/{task_id}/history", "查询执行历史"),
        ("GET", f"/api/open/taskflow/{task_id}/callback", "查询回调信息"),
    ]

    from Implement.hotfixImpl.sealImp import SOPS_HOST

    for method, path, desc in possible_endpoints:
        url = f"{SOPS_HOST}{path}"
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=10)
            else:
                resp = requests.post(url, headers=headers, timeout=10)

            status_code = resp.status_code
            result = resp.json() if resp.text else {}
            success = result.get("result", False)
            state = ""

            # 尝试提取 state
            data = result.get("data", {})
            if isinstance(data, dict):
                state = data.get("state", "")

            mark = "✓" if status_code == 200 and (success or state) else "✗"
            print(f"  {mark} [{status_code}] {method} {path}")
            print(f"      描述: {desc}")
            if state:
                print(f"      状态: {state}")
            if not success and status_code == 200:
                print(f"      消息: {result.get('message', 'N/A')}")

        except requests.exceptions.RequestException as e:
            print(f"  ✗ [ERR] {method} {path}")
            print(f"      描述: {desc}")
            print(f"      异常: {e}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="海豹 (Seal) 任务状态查询与等待完成测试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查询已有任务状态
  python -m tests.test_seal_status query 5273667

  # 等待任务完成
  python -m tests.test_seal_status wait 5273667 --timeout 600 --interval 5

  # 查询任务详情
  python -m tests.test_seal_status detail 5273667

  # 探测可用 API 端点
  python -m tests.test_seal_status probe 5273667

  # 创建新任务并等待
  python -m tests.test_seal_status create DeployTest test_c7

  # 完整流程测试
  python -m tests.test_seal_status full DeployTest test_c7
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # query
    p_query = subparsers.add_parser("query", help="查询任务状态")
    p_query.add_argument("task_id", help="SOPS 任务 ID (即 URL 中的 instance_id)")

    # detail
    p_detail = subparsers.add_parser("detail", help="查询任务详情")
    p_detail.add_argument("task_id", help="SOPS 任务 ID")

    # node_status (已确认此端点返回 404，移除)

    # wait
    p_wait = subparsers.add_parser("wait", help="等待任务完成")
    p_wait.add_argument("task_id", help="SOPS 任务 ID")
    p_wait.add_argument("--timeout", type=float, default=1800, help="超时时间（秒），默认 1800")
    p_wait.add_argument("--interval", type=float, default=10, help="轮询间隔（秒），默认 10")

    # create
    p_create = subparsers.add_parser("create", help="创建并启动任务")
    p_create.add_argument("operation", help="流程名，如 DeployTest, HotfixTest")
    p_create.add_argument("server_name", help="目标服务器/分组名")
    p_create.add_argument("--timeout", type=float, default=0, help="等待超时（秒），0=不等待")
    p_create.add_argument("--interval", type=float, default=10, help="轮询间隔（秒）")

    # full
    p_full = subparsers.add_parser("full", help="完整流程：创建→启动→等待完成")
    p_full.add_argument("operation", help="流程名，如 DeployTest, HotfixTest")
    p_full.add_argument("server_name", help="目标服务器/分组名")

    # probe
    p_probe = subparsers.add_parser("probe", help="探测可用 SOPS API 端点")
    p_probe.add_argument("task_id", help="SOPS 任务 ID (用于探测)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    _ensure_env()
    client = SealClient()

    if args.command == "query":
        cmd_query(client, args.task_id)
    elif args.command == "detail":
        cmd_detail(client, args.task_id)
    elif args.command == "wait":
        cmd_wait(client, args.task_id, args.timeout, args.interval)
    elif args.command == "create":
        cmd_create(client, args.operation, args.server_name, args.timeout, args.interval)
    elif args.command == "full":
        cmd_full(client, args.operation, args.server_name)
    elif args.command == "probe":
        cmd_probe_apis(client, args.task_id)


if __name__ == "__main__":
    main()
