#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hotfix 冲突检查脚本
------------------
通过 P4 pending changelist 号（或本地 lua 文件），检测是否存在函数冲突，
冲突时可选择发送 Kim 消息通知相关提交人。

核心逻辑位于：server/Implement/hotfixImpl/hotfixConflictChecker.py
本脚本仅负责 CLI 参数解析与结果输出。

用法：
  # 检查 CL 12345（自动推断 side，不发 Kim）
  python check_hotfix_conflict.py --changelist 12345

  # 指定 branchType，发送 Kim 消息
  python check_hotfix_conflict.py --changelist 12345 --branchType mainline --notify

  # 强制指定 side
  python check_hotfix_conflict.py --changelist 12345 --side server

  # 直接传入本地 lua 文件进行检查
  python check_hotfix_conflict.py --file /path/to/hotfix_xxx.lua --side server

  # 通过 HTTP 调用后端接口（server 已启动时使用）
  python check_hotfix_conflict.py --changelist 12345 --api http://localhost:16666
"""

import sys
import os
import json
import argparse
import logging

# 添加 server 目录到 Python 路径，以便 import 项目模块
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SERVER_DIR = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _SERVER_DIR)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def _import_checker():
    from Implement.hotfixImpl import hotfixConflictChecker as hcc
    return hcc


def _import_lua_extractor():
    """导入项目中的 lua 函数名提取器，失败时使用 checker 内置的 regex fallback"""
    try:
        from routers.hotfixTool import _extract_func_names_from_lua
        return _extract_func_names_from_lua
    except Exception:
        pass
    # fallback: 使用 checker 自身的 regex
    hcc = _import_checker()
    import re

    def _fallback(lua_content):
        func_mod_pattern = re.compile(r'^([\w.]+)\.(\w+)\s*=\s*function\s*\(')
        func_names = []
        for line in lua_content.strip().split('\n'):
            stripped = line.strip()
            if stripped.startswith('--') or stripped.startswith('print'):
                continue
            m = func_mod_pattern.match(stripped)
            if m:
                func_names.append(f"{m.group(1)}.{m.group(2)}")
        return func_names

    return _fallback


def _get_index_fn(side, branch_type):
    """加载函数名索引，索引不存在时尝试构建"""
    hcc = _import_checker()
    try:
        import config
        branch_dir = 'Mainline' if branch_type == 'mainline' else 'Weekly'
        if side == 'server':
            local_dir = os.path.join(config.P4_WORKSPACE_DIRECTORY, 'C7', 'Development', branch_dir, 'Server', 'hotfix', 'server_hotfix')
        else:
            local_dir = os.path.join(config.P4_WORKSPACE_DIRECTORY, 'C7', 'Development', branch_dir, 'Server', 'hotfix', 'client_hotfix')
        index_file = os.path.join(local_dir, 'hotfix_func_index.json')
        full_index = hcc.load_func_index_from_file(index_file)
        if full_index:
            return full_index
        logger.warning(f"Index not found for {side}/{branch_type}, try building ...")
        try:
            from routers.hotfixTool import _build_hotfix_func_index
            return _build_hotfix_func_index(side, branch_type, notify=False)
        except Exception as e:
            logger.warning(f"Cannot build index: {e}")
            return {}
    except Exception as e:
        logger.warning(f"Cannot load config: {e}")
        return {}


def check_changelist(changelist, branch_type, forced_side, notify):
    hcc = _import_checker()
    extract_fn = _import_lua_extractor()
    return hcc.check_by_changelist(
        changelist=changelist,
        branch_type=branch_type,
        forced_side=forced_side,
        get_index_fn=_get_index_fn,
        extract_func_names_fn=extract_fn,
        notify=notify,
    )


def check_file(file_path, side, branch_type, notify):
    hcc = _import_checker()
    extract_fn = _import_lua_extractor()
    file_name = os.path.basename(file_path)
    with open(file_path, 'r', encoding='utf-8') as f:
        lua_content = f.read()

    full_index = _get_index_fn(side, branch_type)
    result = hcc.check_by_content(
        lua_content=lua_content,
        file_name=file_name,
        side=side,
        branch_type=branch_type,
        full_index=full_index,
        extract_func_names_fn=extract_fn,
        notify=notify,
    )
    return {'fileName': file_name, 'side': side, **result}


def check_via_api(api_base, changelist, branch_type, side):
    try:
        import requests
    except ImportError:
        logger.error("requests library not installed. Run: pip install requests")
        sys.exit(1)

    url = f"{api_base.rstrip('/')}/checkHotfixConflictByChangelist"
    payload = {'changelist': changelist, 'branchType': branch_type}
    if side:
        payload['side'] = side
    logger.info(f"POST {url} payload={payload}")
    resp = requests.post(url, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def print_result(result, is_changelist):
    has_conflict = result.get('hasConflict', False) or bool(result.get('conflicts'))
    print()
    print("=" * 60)
    if is_changelist:
        print(f"CL {result.get('changelist')} 冲突检查结果")
    else:
        print(f"文件 {result.get('fileName')} 冲突检查结果")
    print("=" * 60)

    files = result.get('files') or [result]
    for f in files:
        fn = f.get('fileName', '')
        side = f.get('side', '')
        funcs = f.get('funcNames', [])
        conflicts = f.get('conflicts', [])
        error = f.get('error', '')
        print(f"\n  [{side}] {fn}")
        if error:
            print(f"    ⚠️  Error: {error}")
            continue
        print(f"    函数: {funcs if funcs else '(none)'}")
        if conflicts:
            for c in conflicts:
                print(f"    ❌ 冲突: {c['funcName']} <-> {c['conflictingFiles']}")
        else:
            print("    ✅ 无冲突")

    print()
    notified = result.get('notifiedAuthors', [])
    if has_conflict:
        print(f"❌ 检测到冲突！已通知: {notified if notified else '(未发送 Kim 通知)'}")
    else:
        print("✅ 无冲突")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Hotfix 冲突检查工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python check_hotfix_conflict.py --changelist 12345
  python check_hotfix_conflict.py --changelist 12345 --branchType mainline --notify
  python check_hotfix_conflict.py --file hotfix_xxx.lua --side server
  python check_hotfix_conflict.py --changelist 12345 --api http://localhost:12008
        """
    )
    parser.add_argument('--changelist', type=int, help='P4 pending changelist 号')
    parser.add_argument('--file', type=str, help='本地 lua 文件路径')
    parser.add_argument('--side', choices=['server', 'client'], help='强制指定 side（不传则根据路径自动推断）')
    parser.add_argument('--branchType', default='weekly', choices=['weekly', 'mainline'], help='分支类型 (default: weekly)')
    parser.add_argument('--notify', action='store_true', help='检测到冲突时发送 Kim 消息通知')
    parser.add_argument('--api', type=str, help='后端 API 地址，通过 HTTP 调用接口')
    parser.add_argument('--output', choices=['json', 'text'], default='text', help='输出格式 (default: text)')

    args = parser.parse_args()

    if not args.changelist and not args.file:
        parser.error("必须指定 --changelist 或 --file")

    is_changelist = bool(args.changelist)

    if args.api and args.changelist:
        result = check_via_api(args.api, args.changelist, args.branchType, args.side)
    elif args.file:
        if not args.side:
            parser.error("--file 模式需要指定 --side")
        if not os.path.exists(args.file):
            logger.error(f"File not found: {args.file}")
            sys.exit(1)
        result = check_file(args.file, args.side, args.branchType, args.notify)
    else:
        result = check_changelist(args.changelist, args.branchType, args.side, args.notify)

    if args.output == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_result(result, is_changelist)

    sys.exit(1 if (result.get('hasConflict') or result.get('conflicts')) else 0)


if __name__ == '__main__':
    main()
