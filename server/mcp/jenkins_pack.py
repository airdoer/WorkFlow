# -*- coding: utf-8 -*-
"""
C7 PublicServer 打包触发器（本地 CLI / Skill 共用入口）。

把原 Web 节点 jenkinsDeployExecutor 里的「打包」能力抽成可在 Windows 本地
直接发起的脚本，摆脱前后端依赖。

设计要点：
  1. 零第三方依赖：本地 Python 3.13 未安装 requests，这里用标准库 urllib
     发起 buildWithParameters，并显式禁用系统代理（内网 Jenkins 直连）。
  2. 复用：JENKINS_AUTH / Job 映射 / KIM_NOTIFICATION_TAG 生成逻辑全部来自
     Implement.hotfixImpl.jenkins_config，与 Web 节点同源，不重复定义。
  3. 仅负责「打包」(pack) 这一种操作；热更(hotfix) 仍走原 Web 流程。

分支与 Job 映射（buildWithParameters 地址 = JENKINS_URL/job/<job>/buildWithParameters）：
  mainline  -> Mainline_PublicServer_C7Deploy
  preonline -> Preonline_PublicServer_C7Deploy
  online    -> Online_PublicServer_C7Deploy

CLI 用法示例：
  python jenkins_pack.py --branch mainline                       # 主干包 CL=2333201
  python jenkins_pack.py --branch mainline --version 2333201     # 同上（显式版本）
  python jenkins_pack.py --branch mainline --latest              # 主干最新包(CL 留空)
  python jenkins_pack.py --branch preonline --version 2333201
  python jenkins_pack.py --branch online --version 2333201
  python jenkins_pack.py --branch mainline --trigger-seal        # 例外：勾选触发海豹
  python jenkins_pack.py --branch mainline --dry-run             # 只打印请求，不真正触发

未指定 --version 且未指定 --latest 时，默认使用 2333201（用户约定：说「打一个主干包」即此版本）。
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# 允许脚本被直接执行（python jenkins_pack.py ...）时找到 server 包
_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

from Implement.hotfixImpl.jenkins_config import (  # noqa: E402
    JENKINS_AUTH,
    PUBLIC_SERVER_JENKINS_URL,
    PUBLIC_SERVER_PACK_JOB,
    DEFAULT_PACK_CHANGELIST_ID,
    LATEST_VERSION_TOKEN,
    build_kim_notification_tag,
)

# 显式禁用代理：内网 Jenkins 域名不应被系统 HTTP_PROXY 拐到错误出口
_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def build_request(branch, version=None, latest=False, trigger_seal=False):
    """
    构造一次打包触发的完整请求信息（纯函数，不发网络请求）。

    Args:
        branch: mainline / preonline / online
        version: ChangelistID 版本号；None 表示走默认/最新逻辑
        latest: True -> ChangelistID 留空，tag 版本段用 latest
        trigger_seal: 是否触发海豹，默认 False（不勾选）

    Returns:
        dict: branch/version/job_name/job_url/trigger_url/params/tag
    """
    branch = (branch or "").strip().lower()
    if branch not in PUBLIC_SERVER_PACK_JOB:
        raise ValueError(
            f"未知分支 {branch!r}，可选：{', '.join(PUBLIC_SERVER_PACK_JOB)}"
        )

    if latest:
        changelist_id = ""
        tag_version = LATEST_VERSION_TOKEN
    else:
        changelist_id = str(version).strip() if version not in (None, "") else DEFAULT_PACK_CHANGELIST_ID
        tag_version = changelist_id

    tag = build_kim_notification_tag(branch, tag_version)

    params = {
        "ChangelistID": changelist_id,
        "trigger_seal": "true" if trigger_seal else "false",
        "KIM_NOTIFICATION_TAG": tag,
    }

    job_name = PUBLIC_SERVER_PACK_JOB[branch]
    job_url = f"{PUBLIC_SERVER_JENKINS_URL}/job/{job_name}/"
    trigger_url = f"{job_url}buildWithParameters"

    return {
        "branch": branch,
        "version": tag_version,
        "changelist_id": changelist_id,
        "job_name": job_name,
        "job_url": job_url,
        "trigger_url": trigger_url,
        "params": params,
        "tag": tag,
        "trigger_seal": trigger_seal,
    }


def _basic_auth_header():
    user, token = JENKINS_AUTH
    raw = f"{user}:{token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def trigger(req, timeout=15):
    """
    真正发起 Jenkins buildWithParameters。

    Returns:
        dict: success / job_url / build_number / params / error
    """
    data = urllib.parse.urlencode(req["params"]).encode("utf-8")
    request = urllib.request.Request(req["trigger_url"], data=data, method="POST")
    request.add_header("Authorization", _basic_auth_header())
    request.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        response = _NO_PROXY_OPENER.open(request, timeout=timeout)
        status = response.status
        location = response.headers.get("Location", "") or ""
        response.close()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300] if exc.fp else ""
        return {
            "success": False,
            "error": f"Jenkins 返回 HTTP {exc.code}: {body}",
            "job_url": req["job_url"],
            "params": req["params"],
        }
    except Exception as exc:  # noqa: BLE001 - 网络类异常统一转成结构化结果
        return {
            "success": False,
            "error": f"Jenkins 请求异常: {exc}",
            "job_url": req["job_url"],
            "params": req["params"],
        }

    if status not in (200, 201):
        return {
            "success": False,
            "error": f"Jenkins 请求失败: HTTP {status}",
            "job_url": req["job_url"],
            "params": req["params"],
        }

    build_number = ""
    if location:
        parts = location.rstrip("/").split("/")
        if parts:
            build_number = parts[-1]

    return {
        "success": True,
        "job": req["job_name"],
        "job_url": req["job_url"],
        "build_number": build_number or "pending",
        "queue_url": location,
        "params": req["params"],
        "tag": req["tag"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="触发 C7 PublicServer 打包 Job")
    parser.add_argument(
        "--branch", required=True, choices=sorted(PUBLIC_SERVER_PACK_JOB),
        help="分支：mainline(主干) / preonline / online",
    )
    parser.add_argument("--version", default=None, help="ChangelistID 版本号，如 2333201")
    parser.add_argument(
        "--latest", action="store_true",
        help="打最新包：ChangelistID 留空，KIM_NOTIFICATION_TAG 版本段用 latest",
    )
    parser.add_argument(
        "--trigger-seal", action="store_true",
        help="触发海豹（默认不勾选，即 trigger_seal=false）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只打印将要发起的请求，不真正触发 Jenkins",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args(argv)

    req = build_request(
        branch=args.branch,
        version=args.version,
        latest=args.latest,
        trigger_seal=args.trigger_seal,
    )

    if args.dry_run:
        out = {"dry_run": True, **req}
        if args.json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print("[DRY-RUN] 不会真正触发 Jenkins")
            print(f"  分支        : {req['branch']}")
            print(f"  Job         : {req['job_name']}")
            print(f"  ChangelistID: '{req['changelist_id']}'")
            print(f"  trigger_seal: {req['params']['trigger_seal']}")
            print(f"  TAG         : {req['tag']}")
            print(f"  POST        : {req['trigger_url']}")
            print(f"  params      : {json.dumps(req['params'], ensure_ascii=False)}")
        return 0

    result = trigger(req)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["success"]:
            print(f"[OK] 已触发打包：{result['job']}")
            print(f"  版本/标签 : {req['version']} / {result['tag']}")
            print(f"  构建编号  : {result['build_number']}")
            print(f"  任务页面  : {result['job_url']}")
        else:
            print(f"[FAIL] 触发失败：{result['error']}")
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
