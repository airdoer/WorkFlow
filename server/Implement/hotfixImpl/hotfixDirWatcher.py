"""
Hotfix 目录定时监控器

功能：
1. 每 2 分钟检查 P4 的 Server/hotfix/server_hotfix/ 和 Server/hotfix/client_hotfix/ 目录
2. 用 changelist 号作为版本标识，如果版本变化则重新构建索引并做冲突检测
3. 同样的冲突只通知一次（存储到本地 JSON 文件）
4. 冲突消失了就删掉对应的记录

设计：
- 使用 APScheduler 的 interval cron 来定时触发（与项目现有 timeMgr 机制一致）
- 版本状态存储在 hotfix_dir_watch_state.json
- 已通知冲突存储在 hotfix_conflict_notified.json
- 核心 check 逻辑在 _check_hotfix_dirs_tick() 中，由 cron 调度
"""

import os
import json
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

# ── 配置 ──────────────────────────────────────────────────

# 监控的 P4 目录
# key 格式："side/branch_type"，方便 state 存储和区分分支
_HOTFIX_WATCH_DIRS = {
    'server/weekly':   '//C7/Development/Weekly/Server/hotfix/server_hotfix/',
    'client/weekly':   '//C7/Development/Weekly/Server/hotfix/client_hotfix/',
    'server/mainline': '//C7/Development/Mainline/Server/hotfix/server_hotfix/',
    'client/mainline': '//C7/Development/Mainline/Server/hotfix/client_hotfix/',
}

# 状态文件和已通知冲突文件路径（放在 server/data 目录下）
# 文件位于 server/Implement/hotfixImpl/hotfixDirWatcher.py，需要往上 3 级才能到 server/
_HERE = os.path.abspath(__file__)
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(_HERE))), 'data')
_STATE_FILE = os.path.join(_DATA_DIR, 'hotfix_dir_watch_state.json')
_NOTIFIED_FILE = os.path.join(_DATA_DIR, 'hotfix_conflict_notified.json')
_KIM_GROUP_CONFIG_FILE = os.path.join(_DATA_DIR, 'kim_group_config.json')

# ── 并发保护 ──────────────────────────────────────────────

_check_lock = threading.Lock()
_is_checking = False


def _is_check_running():
    return _is_checking


# ── MongoDB 访问（带 JSON 文件降级兜底） ──────────────────

def _get_mongo():
    """
    获取 HotfixWatcherMongoImp 实例。
    
    每次新建实例以避免 pymongo 连接跨线程复用导致的
    "cannot switch to a different thread" 问题。
    """
    try:
        from dbImp.mongoImp import HotfixWatcherMongoImp
        return HotfixWatcherMongoImp()
    except Exception as e:
        logger.warning(f"hotfixDirWatcher: get mongo failed, fallback to file: {e}")
        return None


# ── 状态管理 ──────────────────────────────────────────────

def _load_state():
    """
    加载版本状态，优先读 MongoDB，失败时降级读 JSON 文件
    
    Returns: {side: changelist_number}
    """
    mongo = _get_mongo()
    if mongo is not None:
        try:
            return mongo.load_state()
        except Exception as e:
            logger.warning(f"hotfixDirWatcher: mongo load_state failed, fallback: {e}")

    # 降级：读 JSON 文件
    if not os.path.exists(_STATE_FILE):
        return {}
    try:
        with open(_STATE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('changelists', {})
    except Exception as e:
        logger.warning(f"hotfixDirWatcher: file load state failed: {e}")
        return {}


def _save_state(changelists):
    """
    保存版本状态，写 MongoDB，同时写 JSON 文件作为备份
    """
    # 写 MongoDB
    mongo = _get_mongo()
    if mongo is not None:
        try:
            mongo.save_state(changelists)
        except Exception as e:
            logger.warning(f"hotfixDirWatcher: mongo save_state failed: {e}")

    # 同步写 JSON 文件（备份 / 降级）
    os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
    data = {
        'changelists': changelists,
        'updated_at': datetime.now().isoformat(),
    }
    try:
        with open(_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"hotfixDirWatcher: file save state failed: {e}")


# ── 已通知冲突管理 ────────────────────────────────────────

def _load_notified_conflicts():
    """
    加载已通知的冲突记录，优先读 MongoDB，失败时降级读 JSON 文件
    
    Returns: dict，格式：
    {
        "server/weekly/FuncName@fileA@fileB": {
            "func_name": "FuncName",
            "side": "server",
            "branch_type": "weekly",
            "conflicting_files": ["fileA", "fileB"],
            "notified_at": "2026-05-20T10:00:00",
            "notified_authors": ["user1", "user2"]
        }
    }
    """
    mongo = _get_mongo()
    if mongo is not None:
        try:
            return mongo.load_notified_conflicts()
        except Exception as e:
            logger.warning(f"hotfixDirWatcher: mongo load_notified_conflicts failed, fallback: {e}")

    # 降级：读 JSON 文件
    if not os.path.exists(_NOTIFIED_FILE):
        return {}
    try:
        with open(_NOTIFIED_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"hotfixDirWatcher: file load notified conflicts failed: {e}")
        return {}


def _save_notified_conflicts(notified):
    """
    保存已通知的冲突记录。
    
    注意：本函数仅用于 JSON 文件的全量备份写入。
    MongoDB 的写入已在 _rebuild_and_notify 中逐条调用
    mongo.upsert_notified_conflict / mongo.delete_notified_conflicts 完成。
    """
    os.makedirs(os.path.dirname(_NOTIFIED_FILE), exist_ok=True)
    try:
        with open(_NOTIFIED_FILE, 'w', encoding='utf-8') as f:
            json.dump(notified, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"hotfixDirWatcher: file save notified conflicts failed: {e}")


def _make_conflict_key(side, branch_type, func_name, conflicting_files):
    """
    生成冲突的唯一 key，用于去重
    
    格式：side/branch_type/func_name@sorted_files
    例如：server/weekly/FashionStationSystem.RequestNavigateTo@hotfix_a_123.lua@hotfix_b_456.lua
    """
    sorted_files = sorted(conflicting_files)
    files_part = '@'.join(sorted_files)
    return f"{side}/{branch_type}/{func_name}@{files_part}"


def _find_new_conflicts(current_conflicts_map, side, branch_type):
    """
    从当前冲突信息中提取所有冲突条目，返回统一的冲突列表
    
    Args:
        current_conflicts_map: _get_all_conflicts_from_index() 的返回值
        side: 'server' | 'client'
        branch_type: 'weekly' | 'mainline'
    
    Returns: list of dict, 每项包含:
        - key: 唯一标识
        - func_name: 冲突函数名
        - conflicting_files: 冲突文件列表
        - file_name: 发现冲突的文件名
    """
    all_conflicts = []
    seen_keys = set()
    for fname, entry in current_conflicts_map.items():
        if not entry.get('conflicts'):
            continue
        # 跳过不带 .lua 后缀的别名 key（_get_all_conflicts_from_index 会注册 fname 和 fname_no_ext，
        # 两者指向同一个 conflict_entry，遍历时会产生重复冲突）
        if not fname.endswith('.lua'):
            continue
        for c in entry['conflicts']:
            func_name = c.get('func_name', '')
            other_files = c.get('conflicting_files', []) or []
            if not func_name or not other_files:
                continue
            # 把当前文件也加入 conflicting_files 列表（构成完整的冲突集合）
            all_files = sorted([fname] + [f for f in other_files if f != fname])
            key = _make_conflict_key(side, branch_type, func_name, all_files)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            all_conflicts.append({
                'key': key,
                'func_name': func_name,
                'conflicting_files': all_files,
                'file_name': fname,
            })
    return all_conflicts


# ── 核心：定时检查 ────────────────────────────────────────

def _get_changelist_for_dir(p4_dir):
    """
    获取 P4 目录的最新 changelist 号

    使用 p4 changes -m 1 <p4_dir>... 查询。
    通过真正的 OS 线程执行，绕过 gevent child watcher 限制。

    Returns: int or None
    """
    # 复用 p4Utils._run_p4，它已在项目中正常工作
    from utility.p4Utils import _run_p4
    p4_path = p4_dir.rstrip('/') + '/...'
    try:
        output = _run_p4(['p4', 'changes', '-m', '1', p4_path])
        if output:
            parts = output.split()
            if len(parts) >= 2 and parts[0] == 'Change':
                return int(parts[1])
    except Exception as e:
        logger.warning(f"hotfixDirWatcher: get changelist for {p4_dir} failed: {e}")
    return None


def check_hotfix_dirs_tick():
    """
    定时检查 P4 hotfix 目录版本变化的回调函数
    
    流程：
    1. 对每个 side（server/client），获取当前 changelist 号
    2. 与上次记录的 changelist 比较
    3. 如果变化了（或有新的 side 需要初始化），触发索引重建 + 冲突检测
    4. 只通知之前未通知过的冲突
    5. 清理已不存在的冲突记录
    """
    global _is_checking
    
    if _is_checking:
        logger.info("hotfixDirWatcher: check already running, skip this tick")
        return
    
    with _check_lock:
        if _is_checking:
            logger.info("hotfixDirWatcher: check already running, skip this tick")
            return
        _is_checking = True
    
    try:
        logger.info("hotfixDirWatcher: tick start")
        
        old_state = _load_state()
        new_state = {}
        need_rebuild_sides = []
        
        # Step 1: 检查每个 side/branch_type 的 changelist 是否变化
        for watch_key, p4_dir in _HOTFIX_WATCH_DIRS.items():
            # watch_key 格式："side/branch_type"，如 "server/weekly"
            side, branch_type = watch_key.split('/', 1)
            current_cl = _get_changelist_for_dir(p4_dir)
            old_cl = old_state.get(watch_key)

            if current_cl is None:
                logger.warning(f"hotfixDirWatcher: cannot get changelist for {watch_key}")
                # P4 超时时保留旧的 changelist，避免下次恢复后误认为首次检查
                new_state[watch_key] = old_cl
                continue

            new_state[watch_key] = current_cl

            if old_cl is None:
                # 首次运行，需要构建索引
                logger.info(f"hotfixDirWatcher: first check for {watch_key}, cl={current_cl}, will build index")
                need_rebuild_sides.append((side, branch_type))
            elif current_cl != old_cl:
                # changelist 变化了，需要重建索引
                logger.info(f"hotfixDirWatcher: {watch_key} changelist changed {old_cl} -> {current_cl}, will rebuild")
                need_rebuild_sides.append((side, branch_type))
            else:
                logger.info(f"hotfixDirWatcher: {watch_key} changelist unchanged (cl={current_cl}), skip")
        
        # 保存新的状态（无论是否需要重建，都记录当前 changelist）
        _save_state(new_state)
        
        if not need_rebuild_sides:
            logger.info("hotfixDirWatcher: no changes detected, tick end")
            return
        
        # Step 2: 对变化的 side 重建索引 + 冲突检测
        # 需要在 Flask app context 中运行（因为使用了 app.logger、p4Utils 等）
        from appImp import app as flask_app
        
        # 整个重建过程都需要 app context（因为 _build_hotfix_func_index 使用了 app.logger）
        with flask_app.app_context():
            for side, branch_type in need_rebuild_sides:
                try:
                    _rebuild_and_notify(side, branch_type)
                except Exception as e:
                    logger.error(f"hotfixDirWatcher: rebuild for {side}/{branch_type} failed: {e}")
        
        logger.info("hotfixDirWatcher: tick end")
        
    except Exception as e:
        logger.error(f"hotfixDirWatcher: tick error: {e}")
    finally:
        _is_checking = False


def _rebuild_and_notify(side, branch_type):
    """
    对指定 side 重建索引，做冲突检测，并只通知新增冲突

    Args:
        side: 'server' | 'client'
        branch_type: 'weekly' | 'mainline'
    """
    from routers.hotfixTool import _incremental_build_hotfix_func_index, _get_all_conflicts_from_index

    result = _incremental_build_hotfix_func_index(side, branch_type, notify=False)
    index_size = result.get('files', 0)

    if not index_size:
        logger.warning(f"hotfixDirWatcher: incremental build returned empty for {side}/{branch_type}")
        return

    logger.info(f"hotfixDirWatcher: index built for {side}/{branch_type}, {index_size} files")

    conflicts_map = _get_all_conflicts_from_index(side, branch_type)
    current_conflicts = _find_new_conflicts(conflicts_map, side, branch_type)

    notified = _load_notified_conflicts()
    new_conflicts = []
    current_keys = set()

    for conflict in current_conflicts:
        key = conflict['key']
        current_keys.add(key)
        if key not in notified:
            new_conflicts.append(conflict)

    prefix = f"{side}/{branch_type}/"
    notified_keys_for_this_side = {k for k in notified.keys() if k.startswith(prefix)}
    removed_keys = list(notified_keys_for_this_side - current_keys)
    if removed_keys:
        logger.info(f"hotfixDirWatcher: {len(removed_keys)} conflicts no longer exist, removing: {removed_keys}")
        mongo = _get_mongo()
        if mongo is not None:
            mongo.delete_notified_conflicts(removed_keys)
        for rk in removed_keys:
            notified.pop(rk, None)

    if new_conflicts:
        logger.info(f"hotfixDirWatcher: {len(new_conflicts)} new conflicts detected for {side}/{branch_type}")
        _notify_new_conflicts(new_conflicts, side, branch_type, notified)

    _save_notified_conflicts(notified)

    logger.info(
        f"hotfixDirWatcher: {side}/{branch_type} check done - "
        f"total_conflicts={len(current_conflicts)}, new={len(new_conflicts)}, removed={len(removed_keys)}"
    )


def _load_notify_group_ids():
    """
    从 kim_group_config.json 读取群聊 ID 列表，多个群 ID 用 ; 分割

    Returns: list of str
    """
    if not os.path.exists(_KIM_GROUP_CONFIG_FILE):
        return []
    try:
        with open(_KIM_GROUP_CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        raw = data.get('group_ids', '')
        if not raw:
            return []
        return [gid.strip() for gid in raw.split(';') if gid.strip()]
    except Exception as e:
        logger.warning(f"hotfixDirWatcher: load kim_group_config failed: {e}")
        return []


def _notify_new_conflicts(new_conflicts, side, branch_type, notified):
    """
    通知新增冲突并通过 Kim 消息发送（含 Redmine QA）
    """
    from utility import p4Utils
    from routers.hotfixTool import _branch_dir_name

    branch_dir = _branch_dir_name(branch_type)
    if not branch_dir:
        return

    if side == 'server':
        p4_dir = f"//C7/Development/{branch_dir}/Server/hotfix/server_hotfix/"
    else:
        p4_dir = f"//C7/Development/{branch_dir}/Server/hotfix/client_hotfix/"

    try:
        hotfix_list = p4Utils.list_dir(p4_dir)
    except Exception:
        hotfix_list = []

    author_map = {}
    cl_map = {}
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
        cl = f.get('changelist', 0) or 0
        if cl:
            cl_map[basename] = cl
            cl_map[basename + '.lua'] = cl
            cl_map[raw_name] = cl

    # 初始化 RedmineMgr
    try:
        from Implement.hotfixImpl.redmineMgr import RedmineMgr
        redmine_mgr = RedmineMgr()
    except Exception as e:
        logger.warning(f"hotfixDirWatcher: import RedmineMgr failed: {e}")
        redmine_mgr = None

    issue_to_qa_kims = {}

    def _get_qa_for_file(fname):
        """从文件对应的 CL 描述里解析 Redmine 单号，再查 QA Kim 用户名"""
        cl = cl_map.get(fname) or cl_map.get(os.path.splitext(fname)[0])
        if not cl or not redmine_mgr:
            return set()
        try:
            desc = p4Utils.get_changelist_description(cl)
            if not desc:
                return set()
            ids = redmine_mgr.extract_issue_ids_from_text(desc)
        except Exception:
            return set()
        qa_users = set()
        for rid in ids:
            if rid not in issue_to_qa_kims:
                try:
                    info = redmine_mgr.get_issue(rid)
                    issue_to_qa_kims[rid] = redmine_mgr.get_qa_kim_usernames(info) if info else []
                except Exception:
                    issue_to_qa_kims[rid] = []
            qa_users.update(issue_to_qa_kims[rid])
        return qa_users

    try:
        from Implement.hotfixImpl.c7KimRobot import C7KimRobot
        kim_robot = C7KimRobot()
    except Exception as e:
        logger.warning(f"hotfixDirWatcher: import C7KimRobot failed: {e}")
        kim_robot = None

    for conflict in new_conflicts:
        key = conflict['key']
        func_name = conflict['func_name']
        conflicting_files = conflict['conflicting_files']

        # 收集 author + QA，同时构建每行文件的 @信息
        target_users = set()
        file_lines = []
        for cf in conflicting_files:
            tags = []
            au = author_map.get(cf) or author_map.get(os.path.splitext(cf)[0])
            if au:
                target_users.add(au)
                tags.append(f"<@=username({au})=>")
            qa_users = _get_qa_for_file(cf)
            if qa_users:
                target_users.update(qa_users)
                tags.extend([f"<@=username({q})=>" for q in sorted(qa_users)])
            tag_str = " " + " ".join(tags) if tags else ""
            file_lines.append(f"- `{cf}`{tag_str}")

        msg_body = (
            f"**⚠️ Hotfix代码与已有hotfix函数冲突 **\n\n"
            f"函数 `{func_name}` 在 `{side}/{branch_type}` 中被以下文件同时修改：\n\n"
            + "\n".join(file_lines)
            + "\n\n请尽快协调处理，避免热更新覆盖问题。"
        )

        notified_authors = []
        if kim_robot and target_users:
            for au in sorted(target_users):
                ok, err = kim_robot.send_msg_to_user(au, msg_body)
                if ok:
                    notified_authors.append(au)
                else:
                    logger.warning(f"hotfixDirWatcher: notify {au} failed: {err}")

        # 推送到配置的群聊
        if kim_robot:
            group_ids = _load_notify_group_ids()
            for gid in group_ids:
                ok, err = kim_robot.send_msg_to_group(gid, msg_body)
                if ok:
                    logger.info(f"hotfixDirWatcher: notified group {gid} for {func_name}")
                else:
                    logger.warning(f"hotfixDirWatcher: notify group {gid} failed: {err}")

        record = {
            'func_name': func_name,
            'side': side,
            'branch_type': branch_type,
            'conflicting_files': conflicting_files,
            'notified_at': datetime.now().isoformat(),
            'notified_authors': notified_authors,
        }
        notified[key] = record

        mongo = _get_mongo()
        if mongo is not None:
            mongo.upsert_notified_conflict(key, record)

        logger.info(
            f"hotfixDirWatcher: notified {func_name} in {side}/{branch_type}, users={notified_authors}"
        )


# ── 初始化：注册 cron ─────────────────────────────────────

def init_hotfix_dir_watcher():
    """
    初始化：在 gevent 主 hub 里起一个 sleep 循环，
    避免 APScheduler BackgroundScheduler 线程导致 subprocess 触发
    "child watchers are only available on the default loop" 错误
    """
    import gevent

    INITIAL_DELAY = 5
    INTERVAL_SEC = 120  # 2 分钟

    def _watcher_loop():
        gevent.sleep(INITIAL_DELAY)
        logger.info("hotfixDirWatcher: greenlet loop started (interval=120s)")
        while True:
            try:
                check_hotfix_dirs_tick()
            except Exception as e:
                logger.error(f"hotfixDirWatcher: loop tick error: {e}")
            gevent.sleep(INTERVAL_SEC)

    logger.info("hotfixDirWatcher: spawning watcher greenlet on main hub")
    gevent.spawn(_watcher_loop)