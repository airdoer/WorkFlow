"""Permission group management API.

Provides CRUD for permission groups, user-node visibility, and pending user management.
Data stored in server/data/auth/permission_groups.json.
"""
import json
import os
import copy
from flask import jsonify, request
from itsdangerous import BadSignature, SignatureExpired
import config
from appImp import app

# ── Data file path ────────────────────────────────────────────────────────────
PERMISSION_FILE = os.environ.get(
    'PERMISSION_GROUPS_FILE',
    os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'auth', 'permission_groups.json')
)


def _ensure_file():
    """Ensure the permission file exists with default content."""
    d = os.path.dirname(PERMISSION_FILE)
    if d:
        os.makedirs(d, exist_ok=True)
    if not os.path.exists(PERMISSION_FILE):
        default = {
            "groups": [
                {
                    "id": "g_all",
                    "name": "基础权限（全员）",
                    "nodeTypes": ["string", "number", "bool", "calculate", "template", "format",
                                  "condition", "if", "loop", "switch", "boolgate", "listbuilder",
                                  "objectbuilder", "dictbuilder", "map", "filter", "reduce", "sort",
                                  "join", "lookup", "split", "distinct", "flatten", "groupby",
                                  "mergeobject", "getglobalvalue", "setglobalvalue", "excel", "json",
                                  "table", "diff", "prompt"],
                    "users": ["*"]
                }
            ],
            "pendingUsers": []
        }
        with open(PERMISSION_FILE, 'w', encoding='utf-8') as f:
            json.dump(default, f, ensure_ascii=False, indent=2)


def _load_data():
    _ensure_file()
    try:
        with open(PERMISSION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"groups": [], "pendingUsers": []}


def _save_data(data):
    d = os.path.dirname(PERMISSION_FILE)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(PERMISSION_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _get_access_token():
    return request.headers.get('Access-Token', '').strip()


def _parse_token(token):
    from routers.auth import _serializer, _parse_token as _auth_parse
    return _auth_parse(token)


def _get_current_username():
    token = _get_access_token()
    return _parse_token(token) if token else ''


def _is_admin(username):
    """Check if user is in admin whitelist."""
    from routers.auth import _load_admin_whitelist
    return username in _load_admin_whitelist()


def _compute_visible_node_types(username, groups):
    """Compute the set of node types visible to a user based on their group memberships."""
    visible = set()
    for g in groups:
        users_in_group = g.get('users', [])
        if '*' in users_in_group or username in users_in_group:
            visible.update(g.get('nodeTypes', []))
    return sorted(visible)


def _add_pending_user(username):
    """Record a user who logged in but has no non-wildcard group membership."""
    data = _load_data()
    existing = [p for p in data.get('pendingUsers', []) if p.get('username') == username]
    if existing:
        # Update loginAt
        existing[0]['loginAt'] = _now_utc()
        _save_data(data)
        return
    # Remove oldest if > 200 pending
    pending = data.get('pendingUsers', [])
    if len(pending) >= 200:
        pending = pending[-199:]
    pending.append({"username": username, "loginAt": _now_utc(), "groups": []})
    data['pendingUsers'] = pending
    _save_data(data)


def _now_utc():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


# ── API Routes ─────────────────────────────────────────────────────────────────

@app.route('/api/permission/groups', methods=['GET'])
def permission_groups():
    """Get all permission groups."""
    username = _get_current_username()
    if not username:
        return jsonify({'message': 'Unauthorized'}), 401
    # Non-admin users can still read groups (to know their own permissions)
    data = _load_data()
    result = []
    for g in data.get('groups', []):
        entry = copy.deepcopy(g)
        # Non-admin users only see group names and their own membership
        if not _is_admin(username):
            entry.pop('users', None)
        result.append(entry)
    return jsonify({'groups': result}), 200


@app.route('/api/permission/group/save', methods=['POST'])
def permission_group_save():
    """Save (create/update/delete) a permission group. Admin only."""
    username = _get_current_username()
    if not username:
        return jsonify({'message': 'Unauthorized'}), 401
    if not _is_admin(username):
        return jsonify({'message': 'Forbidden: admin only'}), 403

    body = request.get_json(silent=True) or {}
    action = body.get('action', 'save')  # save | delete
    group = body.get('group', {})

    data = _load_data()
    groups = data.get('groups', [])

    if action == 'delete':
        group_id = body.get('id', '')
        groups = [g for g in groups if g.get('id') != group_id]
    else:
        group_id = group.get('id', '')
        if not group_id:
            return jsonify({'message': 'Group id is required'}), 400
        # Find and update, or append
        found = False
        for i, g in enumerate(groups):
            if g.get('id') == group_id:
                groups[i] = group
                found = True
                break
        if not found:
            groups.append(group)

    data['groups'] = groups
    _save_data(data)
    return jsonify({'success': True, 'groups': groups}), 200


@app.route('/api/permission/nodes', methods=['GET'])
def permission_nodes():
    """Get all registered node types (for permission editing UI)."""
    username = _get_current_username()
    if not username:
        return jsonify({'message': 'Unauthorized'}), 401

    # Static list matching the frontend NodeRegistry
    node_types = [
        # Data Source
        {"type": "p4file", "name": "P4 文件", "category": "datasource"},
        {"type": "http", "name": "HTTP 请求", "category": "datasource"},
        {"type": "redis", "name": "Redis", "category": "datasource"},
        {"type": "file", "name": "文件", "category": "datasource"},
        {"type": "excelsearch", "name": "Excel 搜索", "category": "datasource"},
        # Collection
        {"type": "map", "name": "Map 映射", "category": "collection"},
        {"type": "filter", "name": "Filter 过滤", "category": "collection"},
        {"type": "reduce", "name": "Reduce 归约", "category": "collection"},
        {"type": "sort", "name": "Sort 排序", "category": "collection"},
        {"type": "join", "name": "Join 合并", "category": "collection"},
        {"type": "lookup", "name": "Lookup 查找", "category": "collection"},
        {"type": "split", "name": "Split 拆分", "category": "collection"},
        {"type": "distinct", "name": "Distinct 去重", "category": "collection"},
        {"type": "flatten", "name": "Flatten 展平", "category": "collection"},
        {"type": "groupby", "name": "GroupBy 分组", "category": "collection"},
        {"type": "mergeobject", "name": "Merge 对象合并", "category": "collection"},
        # Builders
        {"type": "listbuilder", "name": "列表构建", "category": "builder"},
        {"type": "objectbuilder", "name": "对象构建", "category": "builder"},
        {"type": "dictbuilder", "name": "字典构建", "category": "builder"},
        # Expression
        {"type": "calculate", "name": "计算", "category": "expression"},
        {"type": "template", "name": "模板", "category": "expression"},
        {"type": "format", "name": "Format 格式化", "category": "expression"},
        {"type": "condition", "name": "条件", "category": "expression"},
        {"type": "servercommand", "name": "ServerCommand 指令", "category": "tool"},
        # AI
        {"type": "prompt", "name": "Prompt", "category": "ai"},
        {"type": "llm", "name": "LLM", "category": "ai"},
        # Control Flow
        {"type": "if", "name": "If 条件", "category": "controlflow"},
        {"type": "loop", "name": "Loop 循环", "category": "controlflow"},
        {"type": "switch", "name": "Switch 开关", "category": "controlflow"},
        {"type": "boolgate", "name": "BoolGate 门控", "category": "controlflow"},
        # Basic
        {"type": "string", "name": "String 字符串", "category": "basic"},
        {"type": "bool", "name": "Bool 布尔", "category": "basic"},
        {"type": "number", "name": "Number 数值", "category": "basic"},
        # Renderer
        {"type": "excel", "name": "Excel", "category": "renderer"},
        {"type": "json", "name": "JSON", "category": "renderer"},
        {"type": "lua", "name": "Lua", "category": "renderer"},
        {"type": "table", "name": "Table", "category": "renderer"},
        {"type": "diff", "name": "Diff", "category": "renderer"},
        # Tool
        {"type": "c7server", "name": "C7 服务器", "category": "tool"},
        {"type": "seal", "name": "Seal 海豹", "category": "tool"},
        {"type": "jenkinsdeploy", "name": "Jenkins 部署", "category": "tool"},
        {"type": "kdip", "name": "KDIP", "category": "tool"},
        {"type": "kimnotify", "name": "Kim 通知", "category": "tool"},
        {"type": "cron", "name": "Cron 定时", "category": "tool"},
        {"type": "setglobalvalue", "name": "设置全局值", "category": "tool"},
        {"type": "getglobalvalue", "name": "获取全局值", "category": "tool"},
    ]
    return jsonify({'nodes': node_types}), 200


@app.route('/api/permission/user/<username>', methods=['GET'])
def permission_user_nodes(username):
    """Get the visible node types for a specific user."""
    data = _load_data()
    visible = _compute_visible_node_types(username, data.get('groups', []))
    return jsonify({'username': username, 'visibleNodeTypes': visible}), 200


@app.route('/api/permission/pending/list', methods=['GET'])
def permission_pending_list():
    """List pending users (admin only)."""
    username = _get_current_username()
    if not username:
        return jsonify({'message': 'Unauthorized'}), 401
    if not _is_admin(username):
        return jsonify({'message': 'Forbidden: admin only'}), 403
    data = _load_data()
    return jsonify({'pendingUsers': data.get('pendingUsers', [])}), 200


@app.route('/api/permission/pending/assign', methods=['POST'])
def permission_pending_assign():
    """Assign a pending user to groups (admin only)."""
    username = _get_current_username()
    if not username:
        return jsonify({'message': 'Unauthorized'}), 401
    if not _is_admin(username):
        return jsonify({'message': 'Forbidden: admin only'}), 403

    body = request.get_json(silent=True) or {}
    target_user = body.get('username', '')
    group_ids = body.get('groupIds', [])
    if not target_user:
        return jsonify({'message': 'username is required'}), 400

    data = _load_data()
    groups = data.get('groups', [])

    # Add user to specified groups
    for gid in group_ids:
        for g in groups:
            if g.get('id') == gid and target_user not in g.get('users', []):
                if '*' not in g.get('users', []):
                    g.setdefault('users', []).append(target_user)

    # Remove from pending
    data['pendingUsers'] = [p for p in data.get('pendingUsers', []) if p.get('username') != target_user]
    data['groups'] = groups
    _save_data(data)
    return jsonify({'success': True}), 200


@app.route('/api/permission/pending/<target_username>', methods=['DELETE'])
def permission_pending_delete(target_username):
    """Remove a pending user record (admin only)."""
    username = _get_current_username()
    if not username:
        return jsonify({'message': 'Unauthorized'}), 401
    if not _is_admin(username):
        return jsonify({'message': 'Forbidden: admin only'}), 403

    data = _load_data()
    data['pendingUsers'] = [p for p in data.get('pendingUsers', []) if p.get('username') != target_username]
    _save_data(data)
    return jsonify({'success': True}), 200
