import json
import os

import requests
from flask import jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

import config
from appImp import app


def _serializer():
    return URLSafeTimedSerializer(config.AUTH_TOKEN_SECRET, salt='work-flow-auth')


def _generate_token(username: str):
    return _serializer().dumps({'username': username})


def _parse_token(token: str):
    try:
        payload = _serializer().loads(token, max_age=config.AUTH_TOKEN_EXPIRE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    return payload.get('username', '') if payload else None


def _get_access_token():
    return request.headers.get('Access-Token', '').strip()


def _load_admin_whitelist():
    file_path = config.ADMIN_WHITELIST_FILE
    directory = os.path.dirname(file_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as fp:
            json.dump([], fp, ensure_ascii=False)
        return set()

    try:
        with open(file_path, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
    except (json.JSONDecodeError, OSError):
        return set()

    if not isinstance(data, list):
        return set()
    return {str(item).strip() for item in data if str(item).strip()}


def _build_role_info(is_admin: bool):
    role_id = 'admin' if is_admin else 'user'
    role_name = '管理员' if is_admin else '普通用户'
    permissions = [
        {
            'permissionId': 'workflow',
            'permissionName': '工作流',
            'actionEntitySet': []
        }
    ]
    if is_admin:
        permissions.append({
            'permissionId': 'admin',
            'permissionName': '超级管理员',
            'actionEntitySet': []
        })

    return {
        'id': role_id,
        'name': role_name,
        'permissions': permissions
    }


def _fetch_username_from_sso_key(key: str):
    """通过 SSO key 获取用户名"""
    if not key:
        return ''

    authen_get_url = getattr(config, 'AUTHEN_GET_URL', '')
    if not authen_get_url:
        return ''

    try:
        response = requests.get(
            authen_get_url.format(key=key),
            proxies={"http": None, "https": None},
            timeout=5
        )
    except requests.RequestException:
        return ''

    if not response.ok:
        return ''

    return response.text.strip()


@app.route('/api/auth/authen_get', methods=['GET'])
def authen_get():
    """SSO key 换取用户名"""
    key = request.args.get('key', '').strip()
    if not key:
        return jsonify({'message': 'Missing key'}), 400

    username = _fetch_username_from_sso_key(key)
    if not username:
        return jsonify({'result': {'username': ''}, 'user_name': ''}), 200

    return jsonify({'result': {'username': username}, 'user_name': username}), 200


@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """登录接口：支持 username 或 SSO key 登录"""
    payload = request.get_json(silent=True) or {}
    username = str(payload.get('username', '')).strip()
    sso_key = str(payload.get('key', '')).strip()

    if not username and sso_key:
        username = _fetch_username_from_sso_key(sso_key)

    if not username:
        return jsonify({'message': 'username or key is required'}), 400

    token = _generate_token(username)
    return jsonify({'result': {'token': token, 'username': username}}), 200


@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    """退出登录"""
    return jsonify({'result': True}), 200


@app.route('/api/auth/2step-code', methods=['POST'])
def auth_2step_code():
    """二次验证（预留，当前不需要）"""
    return jsonify({'result': {'stepCode': False}}), 200


@app.route('/api/user/info', methods=['GET'])
def get_user_info():
    """获取当前用户信息，admin_whitelist.json 中的用户为超级管理员"""
    token = _get_access_token()
    username = _parse_token(token) if token else ''
    if not username:
        return jsonify({'message': 'Unauthorized', 'result': {'isLogin': False}}), 401

    admins = _load_admin_whitelist()
    is_admin = username in admins
    role_obj = _build_role_info(is_admin)

    # Compute visible node types from permission groups
    visible_node_types = []
    has_non_wildcard_group = False
    try:
        from routers.permission import _load_data, _compute_visible_node_types
        data = _load_data()
        visible_node_types = _compute_visible_node_types(username, data.get('groups', []))
        # Check if user belongs to any non-wildcard group
        for g in data.get('groups', []):
            users_in_group = g.get('users', [])
            if '*' not in users_in_group and username in users_in_group:
                has_non_wildcard_group = True
                break
    except Exception:
        pass

    # If user has no non-wildcard group membership, add to pending
    if not has_non_wildcard_group and not is_admin:
        try:
            from routers.permission import _add_pending_user
            _add_pending_user(username)
        except Exception:
            pass

    return jsonify({
        'result': {
            'name': username,
            'username': username,
            'role': role_obj,
            'is_admin': is_admin,
            'access': 'admin' if is_admin else 'user',
            'visibleNodeTypes': visible_node_types,
            'admins': sorted(admins),
        }
    }), 200


@app.route('/api/user/nav', methods=['GET'])
def get_user_nav():
    """获取用户导航菜单（预留）"""
    return jsonify({'result': []}), 200
