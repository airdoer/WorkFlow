import json
import os

import requests
from flask import jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

import config
from appImp import app


def _serializer():
    return URLSafeTimedSerializer(config.AUTH_TOKEN_SECRET, salt='game-watchman-auth')


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
            'permissionId': 'c7',
            'permissionName': 'C7工具',
            'actionEntitySet': []
        }
    ]
    if is_admin:
        permissions.append({
            'permissionId': 'mail_admin',
            'permissionName': '邮件管理员',
            'actionEntitySet': []
        })

    return {
        'id': role_id,
        'name': role_name,
        'permissions': permissions
    }


def _fetch_username_from_sso_key(key: str):
    if not key:
        return ''

    try:
        response = requests.get(
            config.AUTHEN_GET_URL.format(key=key),
            proxies={"http": None, "https": None},
            timeout=5
        )
    except requests.RequestException:
        return ''

    if not response.ok:
        return ''

    return response.text.strip()


@app.route('/auth/authen_get', methods=['GET'])
def authen_get():
    key = request.args.get('key', '').strip()
    if not key:
        return jsonify({'message': 'Missing key'}), 400

    username = _fetch_username_from_sso_key(key)
    if not username:
        return jsonify({'result': {'username': ''}, 'user_name': ''}), 200

    return jsonify({'result': {'username': username}, 'user_name': username}), 200


@app.route('/auth/login', methods=['POST'])
def auth_login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get('username', '')).strip()
    sso_key = str(payload.get('key', '')).strip()

    if not username and sso_key:
        username = _fetch_username_from_sso_key(sso_key)

    if not username:
        return jsonify({'message': 'username or key is required'}), 400

    token = _generate_token(username)
    return jsonify({'result': {'token': token, 'username': username}}), 200


@app.route('/auth/logout', methods=['POST'])
def auth_logout():
    return jsonify({'result': True}), 200


@app.route('/auth/2step-code', methods=['POST'])
def auth_2step_code():
    return jsonify({'result': {'stepCode': False}}), 200


@app.route('/user/info', methods=['GET'])
def get_user_info():
    token = _get_access_token()
    username = _parse_token(token) if token else ''
    if not username:
        return jsonify({'message': 'Unauthorized', 'result': {'isLogin': False}}), 401

    admins = _load_admin_whitelist()
    is_admin = username in admins
    role_obj = _build_role_info(is_admin)

    return jsonify({
        'result': {
            'name': username,
            'username': username,
            'role': role_obj,
            'is_admin': is_admin
        }
    }), 200


@app.route('/user/nav', methods=['GET'])
def get_user_nav():
    return jsonify({'result': []}), 200
