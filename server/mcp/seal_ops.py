# -*- coding: utf-8 -*-
"""
C7 海豹（Seal / SOPS）操作本地触发器 —— 供 Skill / CLI 直接调用。

把 Web 节点 sealExecutor 的能力抽成 Windows 本地可直接发起的脚本：
对「某台服务器」或「某服务器组」执行「某个海豹操作」（停服/开服/清库/开关外网/
更新代码/改环境变量/hotfix），最终通过 SOPS Open API 创建并启动任务。

设计要点：
  1. 零第三方依赖：本地 Python 3.13 无 requests，HTTP 用标准库 urllib 实现，
     显式禁用系统代理（内网 SOPS 域名直连）。
  2. 复用：数据加载与目标解析复用 sealImp.py 的 SealClient
     （load_seal_operations / resolve_host_ids / _build_request_body）；
     sealImp 已改为 requests 可选导入，本地可安全 import。
  3. 认证：环境变量 SOPS_TOKEN / SOPS_PROJECT 优先，其次读 mcp/sops_local.json。
     sops_local.json 已在 .gitignore 中，禁止入库。
  4. 两步执行：create（建任务）→ start（启动任务），与 Web 节点一致。
  5. --dry-run 只解析与构造请求，不发任何 HTTP。

目标解析：
  - 单台：c7Server.json 的 namespace（key），需有 tree_id
  - 分组：c7ServerTags.json 的组名（key），有 tree_id 直接用，否则展开成员
  - 环境判定（prod/test）：分组取 tag.seal_env，单台取 c7Server.json 的 seal_env

CLI 示例：
  python seal_ops.py --server online --operation 停服 --dry-run
  python seal_ops.py --server c7_online_1101 --operation 开服 --dry-run
  python seal_ops.py --server c7_qa6 --operation 更新代码 --arg source_file=x.tar.gz --arg mode=full --dry-run
  python seal_ops.py --server preview --operation 修改环境变量 --arg mode_type=add --arg key=GAME_MODE --arg value=1 --arg value_type=int --dry-run

操作映射（中文别名 -> c7SealOperation.json 的 key，按环境选择）：见 OP_ALIASES。
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

# 允许脚本被直接执行时找到 server 包
_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

from Implement.hotfixImpl.sealImp import (  # noqa: E402
    SealClient,
    SOPS_HOST,
)
from Implement.hotfixImpl.jenkins_config import PUBLIC_SERVER_JENKINS_URL  # noqa: E402

_MCP_DIR = os.path.dirname(os.path.abspath(__file__))
_AUTH_FILE = os.path.join(_MCP_DIR, "sops_local.json")

# 显式禁用代理：内网 SOPS 域名不应被系统 HTTP_PROXY 拐到错误出口
_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# ── 中文操作别名 -> (prod key, test key) ────────────────────────────────────
# 注意：测试环境停服是 ForceStopTest（非 StopTest），测试环境开服是 StartTest。
OP_ALIASES = {
    "停服": ("StopProd", "ForceStopTest"),
    "关服": ("StopProd", "ForceStopTest"),
    "开服": ("StartProd", "StartTest"),
    "清库": ("ClearDbProd", "ClearDbTest"),
    "清档": ("ClearDbProd", "ClearDbTest"),
    "开关外网": ("FirewallProd", "FirewallTest"),
    "防火墙": ("FirewallProd", "FirewallTest"),
    "更新代码": ("DeployProd", "DeployTest"),
    "更新引擎": ("DeployProd", "DeployTest"),
    "修改环境变量": ("ModifyEnvProd", "ModifyEnvTest"),
    "热更": ("HotfixProd", "HotfixTest"),
    "hotfix": ("HotfixProd", "HotfixTest"),
}

# JSON key 反查环境（用于用户直接给 key 时判定 env）
_KEY_ENV = {}
for _p, _t in OP_ALIASES.values():
    _KEY_ENV[_p] = "prod"
    _KEY_ENV[_t] = "test"


class SealOpsError(Exception):
    """可预期的用户输入/配置错误，CLI 以非 0 退出码并打印 message。"""


# ── 数据加载（复用 SealClient）───────────────────────────────────────────────

def _load_data():
    servers = _client()._load_json('c7Server.json')
    tags = _client()._load_json('c7ServerTags.json')
    if not servers or not tags:
        raise SealOpsError("无法加载 c7Server.json 或 c7ServerTags.json")
    return servers, tags


_ONE_CLIENT = None


def _client():
    global _ONE_CLIENT
    if _ONE_CLIENT is None:
        _ONE_CLIENT = SealClient()
    return _ONE_CLIENT


def list_servers(keyword=None):
    """列出可选服务器/分组（含中文名与环境），供模糊匹配确认。"""
    servers, tags = _load_data()
    kw = (keyword or "").strip().lower()
    out = {"groups": [], "servers": []}
    for name, info in tags.items():
        if kw and kw not in name.lower() and kw not in str(info.get('name', '')).lower():
            continue
        out["groups"].append({
            "key": name, "name": info.get('name', ''),
            "seal_env": info.get('seal_env'), "tree_id": info.get('tree_id'),
            "members": len(info.get('namespaces', [])),
        })
    for name, info in servers.items():
        if kw and kw not in name.lower() and kw not in str(info.get('name', '')).lower():
            continue
        out["servers"].append({
            "key": name, "name": info.get('name', ''),
            "seal_env": info.get('seal_env'), "tree_id": info.get('tree_id'),
            "env": info.get('env'),
        })
    return out


def resolve_server(server):
    """
    解析目标为 (target_envs, host_ids, env, kind, display)。
    server 可为：分组 key / 单台 namespace / 逗号分隔的多台。
    """
    servers, tags = _load_data()
    raw = [s.strip() for s in server.split(',') if s.strip()]
    if not raw:
        raise SealOpsError("server 不能为空")

    kinds, envs = [], []
    for name in raw:
        if name in tags:
            kinds.append("group")
            envs.append(tags[name].get('seal_env'))
        elif name in servers:
            kinds.append("server")
            envs.append(servers[name].get('seal_env'))
        else:
            # 尝试中文名/包含匹配，给出候选
            candidates = []
            for k, info in tags.items():
                if name.lower() in str(info.get('name', '')).lower() or name.lower() in k.lower():
                    candidates.append(f"组:{k}({info.get('name','')})")
            for k, info in servers.items():
                if name.lower() in str(info.get('name', '')).lower() or name.lower() in k.lower():
                    candidates.append(f"服:{k}({info.get('name','')})")
            hint = "；候选：" + "、".join(candidates[:10]) if candidates else ""
            raise SealOpsError(
                f"服务器/分组 '{name}' 不存在（请传 c7Server.json 的 namespace 或 c7ServerTags.json 的组名）{hint}"
            )

    # 环境一致性
    env_set = set(e for e in envs if e)
    if len(env_set) > 1:
        raise SealOpsError(f"目标包含不同环境 {sorted(env_set)}，请拆开执行")
    env = next(iter(env_set)) if env_set else None

    try:
        host_ids = _client().resolve_host_ids(raw)
    except ValueError as exc:
        raise SealOpsError(str(exc))

    kind = "group" if all(k == 'group' for k in kinds) else (
        "server" if all(k == 'server' for k in kinds) else "mixed"
    )
    display = []
    for name in raw:
        info = tags.get(name) or servers.get(name)
        display.append(f"{name}({info.get('name','')})" if info else name)
    return raw, host_ids, env, kind, "、".join(display)


def resolve_operation(operation, env):
    """中文别名或 JSON key -> (op_key, op_info)。env 用于别名选 prod/test。"""
    ops = _client().load_seal_operations()
    if not ops:
        raise SealOpsError("无法加载 c7SealOperation.json")

    op = operation.strip()
    if op in ops:  # 直接给了 json key
        return op, ops[op]
    if op in OP_ALIASES:
        prod_key, test_key = OP_ALIASES[op]
        if env == 'prod':
            key = prod_key
        elif env == 'test':
            key = test_key
        else:
            raise SealOpsError(
                f"目标无法确定 prod/test 环境，无法选择「{op}」的具体流程；"
                f"请直接指定操作 key（如 {prod_key} / {test_key}）"
            )
        if key not in ops:
            raise SealOpsError(f"操作 '{op}' 映射的 '{key}' 在 c7SealOperation.json 中不存在")
        return key, ops[key]

    raise SealOpsError(
        f"未知操作 '{op}'；可选：{'、'.join(OP_ALIASES)}；或直接给 JSON key：{'、'.join(ops)}"
    )


def collect_args(op_info, arg_kv):
    """
    按 args_def 校验并收集参数。
    arg_kv: dict[str, str]，值来自 --arg key=value。
    multiselect 类型按逗号拆成列表。
    """
    args_def = op_info.get('args_def', []) or []
    types = {a.get('key'): a.get('type') for a in args_def}
    required = [a.get('key') for a in args_def if a.get('required')]

    missing = [k for k in required if not arg_kv.get(k)]
    if missing:
        labels = {}
        for a in args_def:
            if a.get('key') in missing:
                labels[a['key']] = a.get('label', a['key'])
        raise SealOpsError(
            "缺少必要参数：" + "、".join(f"{k}({labels.get(k,k)})" for k in missing)
        )

    extra = {}
    for k, v in arg_kv.items():
        if v in (None, ""):
            continue
        if types.get(k) == 'multiselect':
            extra[k] = [x.strip() for x in str(v).split(',') if x.strip()]
        else:
            extra[k] = v
    return extra


# ── 认证 ────────────────────────────────────────────────────────────────────

def load_auth():
    """环境变量优先，其次读 mcp/sops_local.json。返回 (token, project)。"""
    token = os.getenv("SOPS_TOKEN", "") or ""
    project = os.getenv("SOPS_PROJECT", "") or ""
    if token and project:
        return token, project

    file_token, file_project = "", ""
    if os.path.isfile(_AUTH_FILE):
        try:
            with open(_AUTH_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            file_token = str(cfg.get("SOPS_TOKEN", "") or "")
            file_project = str(cfg.get("SOPS_PROJECT", "") or "")
        except Exception as exc:  # noqa: BLE001
            raise SealOpsError(f"读取 {_AUTH_FILE} 失败: {exc}")

    token = token or file_token
    project = project or file_project
    if not token or not project:
        raise SealOpsError(
            "SOPS 认证未配置。请二选一：\n"
            "  1) 设置环境变量 SOPS_TOKEN / SOPS_PROJECT；\n"
            f"  2) 复制 {os.path.join(_MCP_DIR, 'sops_local.example.json')} 为 sops_local.json 并填入真实值。"
        )
    return token, project


def _headers(token, project):
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Project": f"{project}",
        "Request-Id": uuid.uuid4().hex,
    }


# ── 请求构造与执行 ──────────────────────────────────────────────────────────

def build_request(server, operation, arg_kv, executor="chenzhixu"):
    """构造完整请求计划（纯逻辑，不发 HTTP）。"""
    target_envs, host_ids, env, kind, display = resolve_server(server)
    op_key, op_info = resolve_operation(operation, env)
    extra = collect_args(op_info, arg_kv)

    template_id = op_info.get('template_id')
    source_file = op_info.get('source', '')
    script_args = op_info.get('args', '')

    # 与 sealExecutor 一致：source_file 用于替换常量，其余作为 extra constants
    if extra.get('source_file'):
        source_file = extra['source_file']
    sops_extra = {k: v for k, v in extra.items() if k != 'source_file'}

    task_name = f"C7_{op_key}_" + "+".join(target_envs)
    body_str = _client()._build_request_body(
        template_id, host_ids, source_file, script_args, task_name,
        extra_args=sops_extra,
    )

    return {
        "server": server,
        "target_display": display,
        "target_envs": target_envs,
        "target_kind": kind,
        "env": env,
        "operation": op_key,
        "operation_label": op_info.get('label', ''),
        "template_id": template_id,
        "host_ids": host_ids,
        "task_name": task_name,
        "source_file": source_file,
        "script_args": script_args,
        "args": extra,
        "executor": executor,
        "create_url": f"{SOPS_HOST}/api/open/taskflow/create",
        "start_url_tpl": f"{SOPS_HOST}/api/open/taskflow/{{task_id}}/start",
        "create_body": json.loads(body_str),
    }


def _post(url, body, token, project, timeout=30):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in _headers(token, project).items():
        req.add_header(k, v)
    try:
        resp = _NO_PROXY_OPENER.open(req, timeout=timeout)
        text = resp.read().decode("utf-8", errors="replace")
        resp.close()
        return json.loads(text)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300] if exc.fp else ""
        raise SealOpsError(f"SOPS HTTP {exc.code}: {detail}")
    except Exception as exc:  # noqa: BLE001
        raise SealOpsError(f"SOPS 请求异常: {exc}")


def execute(req):
    """真正执行：create + start 两步。"""
    token, project = load_auth()
    create_resp = _post(req["create_url"], req["create_body"], token, project)
    if not create_resp.get("result"):
        raise SealOpsError(f"创建任务失败: {create_resp.get('message', create_resp)}")
    task_id = (create_resp.get("data") or {}).get("task_id")
    if not task_id:
        raise SealOpsError(f"创建任务响应缺少 task_id: {create_resp}")

    start_url = req["start_url_tpl"].format(task_id=task_id)
    start_resp = _post(start_url, {"executor": req["executor"]}, token, project)
    if not start_resp.get("result"):
        raise SealOpsError(f"启动任务失败: {start_resp.get('message', start_resp)}")

    task_url = (start_resp.get("data") or {}).get("task_url", "")
    return {
        "success": True,
        "operation": req["operation"],
        "operation_label": req["operation_label"],
        "target": req["target_display"],
        "env": req["env"],
        "task_id": task_id,
        "task_url": task_url,
        "executor": req["executor"],
        "host_ids": req["host_ids"],
    }


def _parse_args_kv(pairs):
    out = {}
    for item in pairs or []:
        if '=' not in item:
            raise SealOpsError(f"--arg 需为 key=value 形式: {item}")
        k, v = item.split('=', 1)
        out[k.strip()] = v.strip()
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="触发 C7 海豹（SOPS）操作")
    parser.add_argument("--server", default=None,
                        help="目标：单台 namespace 或分组 key（c7Server.json / c7ServerTags.json），逗号分隔可多台")
    parser.add_argument("--operation", default=None,
                        help="操作：中文别名（停服/开服/清库/开关外网/更新代码/修改环境变量/热更）或 JSON key")
    parser.add_argument("--arg", action="append", dest="args", default=[],
                        help="操作参数 key=value，可多次；如 --arg mode=full --arg source_file=x.tar.gz")
    parser.add_argument("--executor", default="chenzhixu", help="SOPS 执行人，默认 chenzhixu")
    parser.add_argument("--dry-run", action="store_true", help="只解析与构造请求，不发 HTTP")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    parser.add_argument("--list", action="store_true",
                        help="列出可选服务器/分组（可配合 --server 关键字过滤），不做其他操作")
    # --server/--operation 在 --list 模式下可选（--server 作为过滤关键字）
    args = parser.parse_args(argv)

    if args.list:
        result = list_servers(args.server if args.server and args.server != '*' else None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if not args.server or not args.operation:
        parser.error("--server 和 --operation 为必填（或使用 --list 查看可选目标）")

    try:
        arg_kv = _parse_args_kv(args.args)
        req = build_request(args.server, args.operation, arg_kv, args.executor)

        if args.dry_run:
            out = {"dry_run": True, **req}
            if args.json:
                print(json.dumps(out, ensure_ascii=False, indent=2))
            else:
                print("[DRY-RUN] 不会真正调用 SOPS")
                print(f"  目标        : {req['target_display']}")
                print(f"  目标类型    : {req['target_kind']}（{'单台' if req['target_kind']=='server' else '服务器组' if req['target_kind']=='group' else '混合'}）")
                print(f"  环境        : {req['env']}")
                print(f"  操作        : {req['operation']}（{req['operation_label']}）")
                print(f"  template_id : {req['template_id']}")
                print(f"  host_ids    : {req['host_ids']}")
                print(f"  task_name   : {req['task_name']}")
                print(f"  args        : {json.dumps(req['args'], ensure_ascii=False)}")
                print(f"  create POST : {req['create_url']}")
                print(f"  create body : {json.dumps(req['create_body'], ensure_ascii=False)}")
            return 0

        result = execute(req)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"[OK] 已触发海豹操作：{result['operation_label']}")
            print(f"  目标    : {result['target']}（{result['env']}）")
            print(f"  task_id : {result['task_id']}")
            print(f"  执行人  : {result['executor']}")
            print(f"  任务页  : {result['task_url']}")
        return 0

    except SealOpsError as exc:
        if args.json:
            print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"[FAIL] {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
