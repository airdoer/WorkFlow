#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hotfix 冲突检查核心逻辑模块
------------------------------
供 hotfixTool.py 路由 和 check_hotfix_conflict.py 脚本共同调用。
"""

import os
import re
import json
import subprocess
import logging

logger = logging.getLogger(__name__)


# ── P4 工具 ──────────────────────────────────────────────────────────────

def _run_p4(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    return result.stdout.strip()


def get_p4_files_in_changelist(changelist):
    """
    通过 p4 describe 获取 CL 中所有 .lua 文件的 depot 路径。

    Returns: list of p4_path strings
    """
    describe_output = _run_p4(["p4", "describe", "-s", str(changelist)])
    if not describe_output:
        logger.error(f"p4 describe returned empty for CL {changelist}")
        return []

    p4_files = []
    in_affected = False
    for line in describe_output.splitlines():
        if line.startswith("Affected files"):
            in_affected = True
            continue
        if in_affected and line.strip().startswith("... "):
            # ... //C7/Development/Weekly/Server/hotfix/server_hotfix/hotfix_xxx.lua#1 edit
            file_part = line.strip()[4:]
            depot_path = file_part.split("#")[0].strip()
            if depot_path.endswith(".lua"):
                p4_files.append(depot_path)
    return p4_files


def get_p4_file_content(p4_path, changelist=None):
    """通过 p4 print -q 获取文件内容，失败时 fallback 到不带 changelist 版本"""
    if changelist:
        content = _run_p4(["p4", "print", "-q", f"{p4_path}@={changelist}"])
        if content:
            return content
    return _run_p4(["p4", "print", "-q", p4_path])


# ── 辅助函数 ──────────────────────────────────────────────────────────────

def infer_side_from_path(p4_path):
    """根据 P4 路径推断 side：server_hotfix → server，client_hotfix → client"""
    if 'server_hotfix' in p4_path:
        return 'server'
    if 'client_hotfix' in p4_path:
        return 'client'
    return None


def extract_hotfix_ticket_key(filename):
    """
    从文件名提取 (author, redmine_id)，用于同单同人豁免。
    规则：hotfix_{name}_{redmineId}.lua 或 hotfix_{name}_{redmineId}_{n}.lua
    """
    name = re.sub(r'\.lua$', '', os.path.basename(filename), flags=re.IGNORECASE)
    m = re.match(r'^hotfix_(.+?)_(\d{5,7})(?:_\d+)?$', name)
    if m:
        return (m.group(1).lower(), m.group(2))
    return None


def is_same_ticket(fname_a, fname_b):
    """同 author + 同 redmine_id 视为同单同人，不计冲突"""
    key_a = extract_hotfix_ticket_key(fname_a)
    key_b = extract_hotfix_ticket_key(fname_b)
    if key_a is None or key_b is None:
        return False
    return key_a == key_b


# ── 索引加载 ──────────────────────────────────────────────────────────────

def load_func_index_from_file(index_file_path):
    """从本地 JSON 文件加载函数名索引"""
    if index_file_path and os.path.exists(index_file_path):
        with open(index_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('index', {})
    return {}


# ── 冲突检查核心 ──────────────────────────────────────────────────────────

def check_conflicts_for_file(file_name, func_names, full_index):
    """
    根据给定函数名列表与已有索引对比，找出冲突的文件。

    Args:
        file_name: 当前文件名（用于排除自身）
        func_names: 当前文件修改的函数名列表
        full_index: {filename: [func_names]} 索引字典

    Returns:
        list of {"funcName": ..., "conflictingFiles": [...]}
    """
    conflicts = []
    for func_name in func_names:
        conflicting_files = []
        for fname, ffuncs in full_index.items():
            if fname == file_name or fname == os.path.splitext(file_name)[0]:
                continue
            if func_name in ffuncs and not is_same_ticket(fname, file_name):
                conflicting_files.append(fname)
        if conflicting_files:
            conflicts.append({
                'funcName': func_name,
                'conflictingFiles': conflicting_files,
            })
    return conflicts


# ── Kim 通知 ──────────────────────────────────────────────────────────────

def build_author_map(side, branch_type):
    """
    从 P4 目录获取 hotfix 文件的 author 映射 {filename: author}。
    依赖 p4Utils，不可用时返回空字典。
    """
    try:
        from utility import p4Utils
    except ImportError:
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
            from utility import p4Utils
        except ImportError:
            logger.warning("p4Utils not available, author map will be empty")
            return {}

    try:
        import config
        branch_dir = 'Mainline' if branch_type == 'mainline' else 'Weekly'
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
        return author_map
    except Exception as e:
        logger.warning(f"build_author_map failed: {e}")
        return {}


def send_kim_notifications_for_conflicts(conflicts_by_side, branch_type, changelist_or_filename,
                                         all_results, cl_submitter=None, app_logger=None):
    """
    发送 Kim 冲突通知，通知范围：
    1. 冲突文件的 P4 author（已提交方）
    2. pending CL 提交者（当事人，仅 changelist 场景）
    3. CL 对应 Redmine 单的 QA 人员（仅 changelist 场景）
    4. kim_group_config.json 中配置的群聊

    Args:
        conflicts_by_side: {side: [{"funcName":..., "conflictingFiles":[...]}]}
        branch_type: 'weekly' | 'mainline'
        changelist_or_filename: CL 号（int）或文件名（str）
        all_results: 文件结果列表，每项含 fileName / side / conflicts
        cl_submitter: pending CL 提交人用户名（str，可选）
        app_logger: 可选，传入 Flask app.logger

    Returns:
        (notified_authors: set, notify_results: list)
    """
    log = app_logger or logger
    notified_authors = set()
    notify_results = []

    try:
        from Implement.hotfixImpl.c7KimRobot import C7KimRobot
        kim_robot = C7KimRobot()
    except Exception as e:
        log.error(f"send_kim_notifications_for_conflicts: cannot import C7KimRobot: {e}")
        return notified_authors, notify_results

    # 加载群聊配置
    group_ids = _load_kim_group_ids()

    # 初始化 RedmineMgr（查 QA）
    redmine_mgr = None
    if isinstance(changelist_or_filename, int):
        try:
            from Implement.hotfixImpl.redmineMgr import RedmineMgr
            redmine_mgr = RedmineMgr()
        except Exception:
            pass

    for conflict_side, side_conflicts in conflicts_by_side.items():
        author_map = build_author_map(conflict_side, branch_type)

        conflict_desc_lines = []
        side_notified = set()

        # 1. 冲突文件的 P4 author（已提交方）
        for c in side_conflicts:
            line = f"- 函数 `{c['funcName']}` 被以下文件同时修改：{', '.join(c['conflictingFiles'])}"
            conflict_desc_lines.append(line)
            for cf in c['conflictingFiles']:
                author = author_map.get(cf) or author_map.get(os.path.splitext(cf)[0])
                if author:
                    side_notified.add(author)
                    notified_authors.add(author)

        # 2. pending CL 提交者（当事人）
        if cl_submitter:
            side_notified.add(cl_submitter)
            notified_authors.add(cl_submitter)

        # 3. Redmine QA
        if isinstance(changelist_or_filename, int) and redmine_mgr:
            qa_users = get_qa_users_for_cl(changelist_or_filename, redmine_mgr, log)
            side_notified.update(qa_users)
            notified_authors.update(qa_users)

        side_files_desc = ", ".join(
            r['fileName'] for r in all_results
            if r.get('side') == conflict_side and r.get('conflicts')
        )

        if isinstance(changelist_or_filename, int):
            header = f"Pending CL `{changelist_or_filename}` 中的文件（{side_files_desc}）"
        else:
            header = f"文件 `{changelist_or_filename}`"

        msg_body = (
            f"**⚠️ Hotfix 函数冲突警告**\n\n"
            f"{header} 在 `{conflict_side}/{branch_type}` 中存在函数冲突：\n\n"
            + "\n".join(conflict_desc_lines)
            + "\n\n请尽快协调处理，避免热更新覆盖问题。"
        )

        # 发送给个人
        for username in sorted(side_notified):
            try:
                success, err = kim_robot.send_msg_to_user(username, msg_body)
                notify_results.append({
                    'username': username,
                    'success': success,
                    'error': err if not success else ''
                })
                if not success:
                    log.warning(f"send_kim_notifications_for_conflicts: notify {username} failed: {err}")
            except Exception as e:
                log.error(f"send_kim_notifications_for_conflicts: notify {username} error: {e}")
                notify_results.append({'username': username, 'success': False, 'error': str(e)})

        # 4. 发送给群聊
        for gid in group_ids:
            try:
                ok, err = kim_robot.send_msg_to_group(gid, msg_body)
                if not ok:
                    log.warning(f"send_kim_notifications_for_conflicts: notify group {gid} failed: {err}")
            except Exception as e:
                log.error(f"send_kim_notifications_for_conflicts: notify group {gid} error: {e}")

    return notified_authors, notify_results


def get_cl_submitter(changelist):
    """
    通过 p4 describe 获取 CL 的提交人用户名。
    pending CL 尚未提交，通过 p4 describe 可以看到 User 字段。
    """
    try:
        output = _run_p4(["p4", "describe", "-s", str(changelist)])
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("User:"):
                return line.split(":", 1)[1].strip()
    except Exception as e:
        logger.warning(f"get_cl_submitter: failed for CL {changelist}: {e}")
    return None


def get_qa_users_for_cl(changelist, redmine_mgr, log=None):
    """
    解析 CL 描述中的 Redmine 单号，查询对应 QA 的 Kim 用户名。

    Returns: set of username strings
    """
    if log is None:
        log = logger
    qa_users = set()
    try:
        output = _run_p4(["p4", "describe", "-s", str(changelist)])
        if not output:
            return qa_users
        # 截取描述文字（User/Date/... 之后、Affected files 之前的部分）
        desc_lines = []
        in_desc = False
        for line in output.splitlines():
            if line.startswith("\t") and not line.strip().startswith("..."):
                in_desc = True
                desc_lines.append(line.strip())
            elif in_desc and line.startswith("Affected files"):
                break
        desc_text = "\n".join(desc_lines)
        issue_ids = redmine_mgr.extract_issue_ids_from_text(desc_text)
        issue_cache = {}
        for rid in issue_ids:
            if rid not in issue_cache:
                try:
                    info = redmine_mgr.get_issue(rid)
                    issue_cache[rid] = redmine_mgr.get_qa_kim_usernames(info) if info else []
                except Exception:
                    issue_cache[rid] = []
            qa_users.update(issue_cache[rid])
    except Exception as e:
        log.warning(f"get_qa_users_for_cl: failed for CL {changelist}: {e}")
    return qa_users


def _load_kim_group_ids():
    """从 kim_group_config.json 读取群聊 ID 列表"""
    _here = os.path.abspath(__file__)
    _data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(_here))), 'data')
    group_config_file = os.path.join(_data_dir, 'kim_group_config.json')
    if not os.path.exists(group_config_file):
        return []
    try:
        with open(group_config_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        raw = data.get('group_ids', '')
        if not raw:
            return []
        return [gid.strip() for gid in raw.split(';') if gid.strip()]
    except Exception as e:
        logger.warning(f"_load_kim_group_ids failed: {e}")
        return []


# ── 高级入口：按内容检查 ──────────────────────────────────────────────────

def check_by_content(lua_content, file_name, side, branch_type,
                     full_index, extract_func_names_fn, notify=True, app_logger=None):
    """
    对给定 lua 内容进行冲突检查，可选发送 Kim 通知。

    Args:
        lua_content: lua 文件文本内容
        file_name: 文件名（用于排除自身、消息描述）
        side: 'server' | 'client'
        branch_type: 'weekly' | 'mainline'
        full_index: 已加载的函数名索引
        extract_func_names_fn: 从 lua 内容提取函数名的函数
        notify: 是否发送 Kim 通知
        app_logger: 可选 Flask logger

    Returns:
        dict with keys: funcNames, conflicts, notifiedAuthors, notifyResults
    """
    func_names = extract_func_names_fn(lua_content)
    conflicts = check_conflicts_for_file(file_name, func_names, full_index)

    notified_authors = set()
    notify_results = []
    if conflicts and notify:
        notified_authors, notify_results = send_kim_notifications_for_conflicts(
            {side: conflicts},
            branch_type,
            file_name,
            [{'fileName': file_name, 'side': side, 'conflicts': conflicts}],
            app_logger=app_logger,
        )

    return {
        'funcNames': func_names,
        'conflicts': conflicts,
        'notifiedAuthors': list(sorted(notified_authors)),
        'notifyResults': notify_results,
    }


# ── 高级入口：按 changelist 检查 ─────────────────────────────────────────

def check_by_changelist(changelist, branch_type, forced_side,
                        get_index_fn, extract_func_names_fn,
                        notify=True, app_logger=None):
    """
    对 pending CL 中的所有 lua 文件做冲突检查，可选发送 Kim 通知。

    Args:
        changelist: int，P4 CL 号
        branch_type: 'weekly' | 'mainline'
        forced_side: None 或 'server'/'client'，None 则自动推断
        get_index_fn: 接受 (side, branch_type) 返回 full_index 的函数
        extract_func_names_fn: 从 lua 内容提取函数名的函数
        notify: 是否发送 Kim 通知
        app_logger: 可选 Flask logger

    Returns:
        dict with keys: changelist, files, hasConflict, notifiedAuthors, notifyResults
    """
    log = app_logger or logger

    p4_files = get_p4_files_in_changelist(changelist)
    if not p4_files:
        return {'changelist': changelist, 'files': [], 'hasConflict': False, 'notifiedAuthors': [], 'notifyResults': []}

    index_cache = {}

    def _cached_index(side):
        if side not in index_cache:
            index_cache[side] = get_index_fn(side, branch_type)
        return index_cache[side]

    all_results = []
    all_conflicts_by_side = {}

    for p4_path in p4_files:
        file_name = p4_path.split("/")[-1]
        side = forced_side or infer_side_from_path(p4_path)

        if not side:
            log.warning(f"check_by_changelist: cannot infer side for {p4_path}, skipping")
            all_results.append({
                'fileName': file_name, 'p4Path': p4_path, 'side': None,
                'funcNames': [], 'conflicts': [],
                'error': 'Cannot infer side from path (not in server_hotfix or client_hotfix)'
            })
            continue

        lua_content = get_p4_file_content(p4_path, changelist)
        if not lua_content:
            log.warning(f"check_by_changelist: empty content for {p4_path}, skipping")
            all_results.append({
                'fileName': file_name, 'p4Path': p4_path, 'side': side,
                'funcNames': [], 'conflicts': [], 'error': 'Empty content'
            })
            continue

        full_index = _cached_index(side)
        func_names = extract_func_names_fn(lua_content)
        conflicts = check_conflicts_for_file(file_name, func_names, full_index)

        all_results.append({
            'fileName': file_name,
            'p4Path': p4_path,
            'side': side,
            'funcNames': func_names,
            'conflicts': conflicts,
        })

        if conflicts:
            if side not in all_conflicts_by_side:
                all_conflicts_by_side[side] = []
            all_conflicts_by_side[side].extend(conflicts)

    has_conflict = len(all_conflicts_by_side) > 0
    notified_authors = set()
    notify_results = []
    if has_conflict and notify:
        cl_submitter = get_cl_submitter(changelist)
        notified_authors, notify_results = send_kim_notifications_for_conflicts(
            all_conflicts_by_side, branch_type, changelist, all_results,
            cl_submitter=cl_submitter, app_logger=log,
        )

    return {
        'changelist': changelist,
        'files': all_results,
        'hasConflict': has_conflict,
        'notifiedAuthors': list(sorted(notified_authors)),
        'notifyResults': notify_results,
    }
