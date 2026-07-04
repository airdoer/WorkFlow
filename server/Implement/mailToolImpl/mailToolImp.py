import json
import logging
import os
from datetime import datetime, timedelta, timezone
from threading import Lock
from Implement.mailToolImpl.kimRobotImp import KimRobot
from Implement.mailToolImpl.mailDispatchImp import MailDispatchImp

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

import config
from Implement.kdipServerImpl.kdipServerImp import KdipServer, EnvironmentTypes, KdipCodeStatusTypes
from dbImp.mongoImp import get_mail_mongo


logger = logging.getLogger(__name__)


MAIL_CREATE_OP_CODE = 1
MAIL_REVIEW_OP_CODE = 2
MAIL_PASS_OP_CODE = 3
MAIL_AUTO_OP_CODE = 4
MAIL_DELETE_OP_CODE = 5
MAIL_EDIT_OP_CODE = 6
MAIL_RECALL_OP_CODE = 7
MAIL_REJECT_OP_CODE = 8
MAIL_STATUS_PENDING_SUBMIT = 'pending_submit'
MAIL_STATUS_PENDING_APPROVE = 'pending_approve'
MAIL_STATUS_PENDING_EFFECT = 'pending_effect'
MAIL_STATUS_IN_EFFECT = 'in_effect'
MAIL_STATUS_EXPIRED = 'expired'
MAIL_STALE_VERSION_CODE = 'MAIL_STALE_VERSION'
MAIL_STALE_VERSION_MESSAGE = '状态非最新，请刷新后重试'
MAIL_META_DEFAULT = {
    'next_mail_id': 1,
    'mail_ids': []
}


_mail_file_lock = Lock()
BEIJING_TZ = timezone(timedelta(hours=8))
_channel_mapping_cache = {
    'file': '',
    'mtime': 0,
    'map': {}
}


def _mail_mongo():
    return get_mail_mongo()


def load_mail_meta_from_db():
    return _mail_mongo().load_mail_meta()


def save_mail_meta_to_db(meta):
    return _mail_mongo().save_mail_meta(meta)


def load_mail_record_from_db(mail_id):
    return _mail_mongo().load_mail_record(mail_id)


def save_mail_record_to_db(mail_record):
    return _mail_mongo().save_mail_record(mail_record)


def delete_mail_record_from_db(mail_id):
    return _mail_mongo().delete_mail_record(mail_id)


def list_mail_ids_from_db():
    return _mail_mongo().list_mail_ids()


def list_mail_records_from_db(status='', server_env_type='', skip=0, limit=20, sort_by='mail_id', sort_order='desc'):
    return _mail_mongo().list_mail_records(
        status=status,
        server_env_type=server_env_type,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order
    )


def load_mail_templates_from_db():
    return _mail_mongo().load_mail_templates()


def save_mail_templates_to_db(templates):
    return _mail_mongo().save_mail_templates(templates)


def _parse_list_query_values(query_args, key):
    if hasattr(query_args, 'getlist'):
        values = query_args.getlist(key)
    else:
        raw = query_args.get(key)
        values = raw if isinstance(raw, list) else [raw]

    parsed = []
    for value in values:
        text = str(value or '').strip()
        if not text:
            continue
        parsed.extend([item.strip() for item in text.split(',') if item.strip()])

    unique_values = []
    seen = set()
    for item in parsed:
        if item in seen:
            continue
        seen.add(item)
        unique_values.append(item)
    return unique_values


def now_str():
    return datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M:%S')


def _parse_datetime_to_bj(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        text = text.replace('Z', '+00:00')
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=BEIJING_TZ)
    return dt.astimezone(BEIJING_TZ)


def _serializer():
    return URLSafeTimedSerializer(config.AUTH_TOKEN_SECRET, salt='game-watchman-auth')


def parse_username_from_token(token: str):
    try:
        payload = _serializer().loads(token, max_age=config.AUTH_TOKEN_EXPIRE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    return payload.get('username', '') if payload else None


def _load_mail_meta():
    try:
        db_meta = load_mail_meta_from_db()
        if isinstance(db_meta, dict):
            return db_meta
    except Exception as err:
        logger.warning('load mail meta from db failed. err=%s', err)
        return dict(MAIL_META_DEFAULT)

    return dict(MAIL_META_DEFAULT)


def _save_mail_meta(meta):
    try:
        save_mail_meta_to_db(meta)
    except Exception as err:
        logger.warning('save mail meta to db failed. err=%s', err)


def _load_admin_whitelist():
    file_path = config.ADMIN_WHITELIST_FILE
    directory = os.path.dirname(file_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    if not os.path.exists(file_path):
        return set()

    try:
        with open(file_path, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
    except (OSError, json.JSONDecodeError) as err:
        logger.warning('load admin whitelist failed. file=%s err=%s', file_path, err)
        return set()

    if not isinstance(data, list):
        return set()
    return {str(item).strip() for item in data if str(item).strip()}


def _safe_int(value, default_value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default_value

def _extract_env_type_from_region(region_value):
    region_text = str(region_value or '').strip().lower()
    if not region_text:
        return ''
    if region_text == 'online' or region_text.startswith('online|'):
        return 'online'
    if region_text == 'debugging' or region_text.startswith('debugging|'):
        return 'debugging'
    return ''

def _resolve_record_env_types(record):
    values = set()
    if not isinstance(record, dict):
        return values

    env_list = record.get('serverEnvTypes', [])
    if isinstance(env_list, list):
        for item in env_list:
            text = str(item or '').strip().lower()
            if text:
                values.add(text)

    region_env = _extract_env_type_from_region(record.get('region'))
    if region_env:
        values.add(region_env)

    return values


def _load_mail_record(mail_id: int):
    try:
        db_record = load_mail_record_from_db(mail_id)
        if isinstance(db_record, dict):
            return db_record
    except Exception as err:
        logger.warning('load mail record from db failed. mail_id=%s err=%s', mail_id, err)
        return None

    return None


def _save_mail_record(mail_record):
    mail_id = _safe_int(mail_record.get('mailId'), 0)
    if mail_id <= 0:
        return False

    try:
        return bool(save_mail_record_to_db(mail_record))
    except Exception as err:
        logger.error('save mail record to db failed. mail_id=%s err=%s', mail_id, err)
        return False


def _apply_auto_state_progress(record):
    if not isinstance(record, dict):
        return record, False

    status = str(record.get('status', '')).strip()
    history = record.get('operationHistory', [])
    if not isinstance(history, list):
        history = []

    changed = False
    now_dt = datetime.now(BEIJING_TZ)

    while True:
        if status == MAIL_STATUS_PENDING_EFFECT:
            scheduled_dt = _parse_datetime_to_bj(record.get('scheduledTime'))
            if scheduled_dt and scheduled_dt <= now_dt:
                history.append(_build_operation_history(
                    MAIL_AUTO_OP_CODE,
                    'auto_effect',
                    'system',
                    MAIL_STATUS_PENDING_EFFECT,
                    MAIL_STATUS_IN_EFFECT,
                    '到达生效时间，自动进入生效中'
                ))
                status = MAIL_STATUS_IN_EFFECT
                record['status'] = status
                changed = True
                continue

        if status == MAIL_STATUS_IN_EFFECT:
            expire_dt = _parse_datetime_to_bj(record.get('expireTime'))
            if expire_dt and expire_dt <= now_dt:
                history.append(_build_operation_history(
                    MAIL_AUTO_OP_CODE,
                    'auto_expire',
                    'system',
                    MAIL_STATUS_IN_EFFECT,
                    MAIL_STATUS_EXPIRED,
                    '达到过期时间，自动进入已过期'
                ))
                status = MAIL_STATUS_EXPIRED
                record['status'] = status
                changed = True
                continue

        break

    if changed:
        record['operationHistory'] = history
        record['updateTime'] = now_str()

    return record, changed


def _load_mail_record_with_auto_progress(mail_id: int):
    record = _load_mail_record(mail_id)
    if not record:
        return None

    updated_record, changed = _apply_auto_state_progress(record)
    if changed:
        _save_mail_record(updated_record)
    return updated_record


def _resolve_mail_ids(meta):
    mail_ids = meta.get('mail_ids', []) if isinstance(meta, dict) else []
    if isinstance(mail_ids, list) and len(mail_ids) > 0:
        valid_ids = []
        for mail_id in mail_ids:
            try:
                valid_ids.append(int(mail_id))
            except (TypeError, ValueError):
                continue
        if valid_ids:
            return sorted(set(valid_ids), reverse=True)

    try:
        db_ids = list_mail_ids_from_db()
        if db_ids:
            return db_ids
    except Exception as err:
        logger.warning('resolve mail ids from db failed. err=%s', err)
    return []


def _normalize_mail_payload(data):
    if not isinstance(data, dict):
        return None, 'data must be an object'

    required_fields = ['taskName', 'title', 'content', 'expireTime']
    for field in required_fields:
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            return None, f'{field} is required'

    rewards = data.get('rewards', [])
    if rewards is None:
        rewards = []
    if not isinstance(rewards, list):
        return None, 'rewards must be an array'

    servers = data.get('servers', [])
    if servers is None:
        servers = []
    if not isinstance(servers, list):
        return None, 'servers must be an array'

    server_env_types = data.get('serverEnvTypes', [])
    if server_env_types is None:
        server_env_types = []
    if not isinstance(server_env_types, list):
        return None, 'serverEnvTypes must be an array'

    server_env_map = data.get('serverEnvMap', [])
    if server_env_map is None:
        server_env_map = []
    if not isinstance(server_env_map, list):
        return None, 'serverEnvMap must be an array'

    normalized = {
        'templateId': data.get('templateId'),
        'taskName': str(data.get('taskName', '')).strip(),
        'title': str(data.get('title', '')).strip(),
        'content': str(data.get('content', '')).strip(),
        'region': data.get('region'),
        'channel': data.get('channel'),
        'subChannel': data.get('subChannel'),
        'sendDimension': data.get('sendDimension') or 'server',
        'servers': servers,
        'serverEnvTypes': [str(item).strip() for item in server_env_types if str(item).strip()],
        'serverEnvMap': [item for item in server_env_map if isinstance(item, dict)],
        'roleIds': str(data.get('roleIds', '')).strip(),
        'scheduledTime': data.get('scheduledTime'),
        'expireTime': data.get('expireTime'),
        'useScheduledAsReceiveTime': bool(data.get('useScheduledAsReceiveTime', False)),
        'validDuration': data.get('validDuration', -1),
        'sender': str(data.get('sender', '')).strip(),
        'minLevel': data.get('minLevel'),
        'createTimeCondition': data.get('createTimeCondition'),
        'addToFav': bool(data.get('addToFav', False)),
        'rewards': rewards,
        'recipientType': 'role' if (data.get('sendDimension') == 'role') else 'server'
    }

    if not normalized['serverEnvTypes']:
        region_env = _extract_env_type_from_region(normalized.get('region'))
        if region_env:
            normalized['serverEnvTypes'] = [region_env]

    return normalized, ''


def _build_create_history(operator: str, copy_from_mail_id=None):
    is_copy = copy_from_mail_id is not None
    return {
        'opCode': MAIL_CREATE_OP_CODE,
        'opName': 'copy' if is_copy else 'create',
        'fromStatus': None,
        'toStatus': MAIL_STATUS_PENDING_SUBMIT,
        'operator': operator,
        'operateAt': now_str(),
        'comment': f'复制邮件({copy_from_mail_id})并新建' if is_copy else '新建邮件'
    }


def _build_operation_history(op_code: int, op_name: str, operator: str, from_status, to_status, comment=''):
    return {
        'opCode': op_code,
        'opName': op_name,
        'fromStatus': from_status,
        'toStatus': to_status,
        'operator': operator,
        'operateAt': now_str(),
        'comment': comment
    }


def _is_admin(username: str):
    if not username:
        return False
    return username in _load_admin_whitelist()


def _extract_mail_id(payload):
    mail_id = payload.get('mail_id')
    if mail_id is None:
        mail_id = payload.get('mailId')
    if mail_id is None and isinstance(payload.get('data'), dict):
        data = payload.get('data')
        mail_id = data.get('mailId', data.get('id'))
    return _safe_int(mail_id, 0)


def _extract_expected_update_time(payload):
    if not isinstance(payload, dict):
        return ''

    expected_update_time = payload.get('expected_update_time')
    if expected_update_time is None:
        expected_update_time = payload.get('expectedUpdateTime')

    data = payload.get('data')
    if expected_update_time is None and isinstance(data, dict):
        expected_update_time = data.get('expected_update_time', data.get('expectedUpdateTime'))

    if expected_update_time is None:
        return ''
    return str(expected_update_time).strip()


def _validate_mail_record_freshness(record, expected_update_time):
    expected = str(expected_update_time or '').strip()
    if not expected:
        return False, 'expected_update_time is required', ''

    latest = str((record or {}).get('updateTime', '')).strip()
    if latest != expected:
        return False, MAIL_STALE_VERSION_MESSAGE, MAIL_STALE_VERSION_CODE

    return True, '', ''


def extract_mail_id_from_payload(payload):
    return _extract_mail_id(payload)


def _can_edit_mail(record, username, is_admin):
    status = str(record.get('status', '')).strip()
    creator = str(record.get('creator', '')).strip()

    if status not in [MAIL_STATUS_PENDING_SUBMIT, MAIL_STATUS_PENDING_APPROVE]:
        return False, f'编辑仅支持 {MAIL_STATUS_PENDING_SUBMIT}/{MAIL_STATUS_PENDING_APPROVE} 状态'

    if is_admin or creator == username:
        return True, ''

    return False, '无编辑权限，仅管理员或邮件发起者可编辑'


def _can_delete_mail(record, username, is_admin):
    status = str(record.get('status', '')).strip()
    creator = str(record.get('creator', '')).strip()

    if status == MAIL_STATUS_PENDING_SUBMIT:
        if is_admin or creator == username:
            return True, ''
        return False, '无删除权限，待提审邮件仅管理员或发起者可删除'

    if status == MAIL_STATUS_EXPIRED:
        if is_admin:
            return True, ''
        return False, '无删除权限，已失效邮件仅管理员可删除'

    return False, '当前状态不允许删除，仅待提审/已过期状态可删除'


def _can_review_mail(record, username, is_admin):
    status = str(record.get('status', '')).strip()
    creator = str(record.get('creator', '')).strip()

    if status != MAIL_STATUS_PENDING_SUBMIT:
        return False, f'提审仅支持 {MAIL_STATUS_PENDING_SUBMIT} 状态'

    if is_admin or creator == username:
        return True, ''

    return False, '无提审权限，仅管理员或邮件发起者可提审'


def _can_pass_mail(record, is_admin):
    status = str(record.get('status', '')).strip()

    if status != MAIL_STATUS_PENDING_APPROVE:
        return False, f'通过仅支持 {MAIL_STATUS_PENDING_APPROVE} 状态'

    if is_admin:
        return True, ''

    return False, '无通过权限，仅管理员可通过'


def _can_reject_mail(record, is_admin):
    status = str(record.get('status', '')).strip()

    if status != MAIL_STATUS_PENDING_APPROVE:
        return False, f'驳回仅支持 {MAIL_STATUS_PENDING_APPROVE} 状态'

    if is_admin:
        return True, ''

    return False, '无驳回权限，仅管理员可驳回'


def _can_recall_mail(record, username, is_admin):
    status = str(record.get('status', '')).strip()
    creator = str(record.get('creator', '')).strip()

    if status == MAIL_STATUS_PENDING_APPROVE:
        if creator == username:
            return True, '', MAIL_STATUS_PENDING_SUBMIT, '撤回待审批邮件'
        return False, '无撤回权限，待审批邮件仅发起者可撤回', '', ''

    if status == MAIL_STATUS_PENDING_EFFECT:
        if is_admin:
            return True, '', MAIL_STATUS_PENDING_SUBMIT, '撤回待生效邮件（待生效->待提审）'
        return False, '无撤回权限，待生效邮件仅管理员可撤回', '', ''

    return False, f'撤回仅支持 {MAIL_STATUS_PENDING_APPROVE}/{MAIL_STATUS_PENDING_EFFECT} 状态', '', ''


def create_mail_record(operator: str, data: dict):
    normalized, err_msg = _normalize_mail_payload(data)
    if err_msg:
        return None, err_msg

    with _mail_file_lock:
        meta = _load_mail_meta()
        mail_id = meta['next_mail_id']
        now = now_str()
        copy_from_mail_id = _safe_int(data.get('copyFromMailId'), 0)
        if copy_from_mail_id <= 0:
            copy_from_mail_id = None

        mail_record = {
            'mailId': mail_id,
            'status': MAIL_STATUS_PENDING_SUBMIT,
            'creator': operator,
            'creatorName': operator,
            'createTime': now,
            'updateTime': now,
            **normalized,
            'operationHistory': [_build_create_history(operator, copy_from_mail_id)]
        }

        if not _save_mail_record(mail_record):
            return None, 'save mail record failed'

        meta['next_mail_id'] = mail_id + 1
        meta['mail_ids'].append(mail_id)
        _save_mail_meta(meta)

    logger.info('mail created. mail_id=%s operator=%s status=%s', mail_record.get('mailId'), operator, mail_record.get('status'))

    return mail_record, ''


def edit_mail_record(operator: str, mail_id: int, data: dict, expected_update_time=''):
    if mail_id <= 0:
        return None, 'mail_id is required', ''

    normalized, err_msg = _normalize_mail_payload(data)
    if err_msg:
        return None, err_msg, ''

    with _mail_file_lock:
        record = _load_mail_record_with_auto_progress(mail_id)
        if not record:
            return None, f'mail({mail_id}) not found', ''

        is_fresh, stale_msg, stale_code = _validate_mail_record_freshness(record, expected_update_time)
        if not is_fresh:
            return None, stale_msg, stale_code

        is_admin = _is_admin(operator)
        can_edit, deny_msg = _can_edit_mail(record, operator, is_admin)
        if not can_edit:
            return None, deny_msg, ''

        old_status = record.get('status', MAIL_STATUS_PENDING_SUBMIT)
        history = record.get('operationHistory', [])
        if not isinstance(history, list):
            history = []

        next_status = old_status
        comment = '编辑邮件'
        if old_status == MAIL_STATUS_PENDING_APPROVE:
            next_status = MAIL_STATUS_PENDING_SUBMIT
            comment = '待审批邮件编辑后回到待提审'

        updated_record = {
            **record,
            **normalized,
            'mailId': record.get('mailId', mail_id),
            'creator': record.get('creator', operator),
            'creatorName': record.get('creatorName', record.get('creator', operator)),
            'status': next_status,
            'createTime': record.get('createTime', now_str()),
            'updateTime': now_str()
        }
        history.append(_build_operation_history(
            MAIL_EDIT_OP_CODE,
            'edit',
            operator,
            old_status,
            next_status,
            comment
        ))
        updated_record['operationHistory'] = history

        if not _save_mail_record(updated_record):
            return None, 'save edited mail record failed', ''

    logger.info('mail edited. mail_id=%s operator=%s from_status=%s to_status=%s', mail_id, operator, old_status, next_status)

    return updated_record, '', ''


def delete_mail_record(operator: str, mail_id: int, expected_update_time=''):
    if mail_id <= 0:
        return None, 'mail_id is required', ''

    with _mail_file_lock:
        record = _load_mail_record_with_auto_progress(mail_id)
        if not record:
            return None, f'mail({mail_id}) not found', ''

        is_fresh, stale_msg, stale_code = _validate_mail_record_freshness(record, expected_update_time)
        if not is_fresh:
            return None, stale_msg, stale_code

        is_admin = _is_admin(operator)
        can_delete, deny_msg = _can_delete_mail(record, operator, is_admin)
        if not can_delete:
            return None, deny_msg, ''

        try:
            db_deleted = delete_mail_record_from_db(mail_id)
        except Exception as err:
            db_deleted = False
            logger.error('delete mail record in db failed. mail_id=%s err=%s', mail_id, err)
        if not db_deleted:
            return None, 'delete mail db record failed', ''

        meta = _load_mail_meta()
        mail_ids = meta.get('mail_ids', [])
        if isinstance(mail_ids, list):
            normalized_ids = []
            for value in mail_ids:
                as_int = _safe_int(value, 0)
                if as_int > 0 and as_int != mail_id:
                    normalized_ids.append(as_int)
            meta['mail_ids'] = normalized_ids
            _save_mail_meta(meta)

    logger.info('mail deleted. mail_id=%s operator=%s', mail_id, operator)

    return {
        'mailId': mail_id,
        'deleted': True
    }, '', ''


def change_mail_status(operator: str, mail_id: int, op_code: int, expected_update_time=''):
    if mail_id <= 0:
        return None, 'mail_id is required', ''

    need_notify_review = False
    need_notify_passed = False

    with _mail_file_lock:
        record = _load_mail_record_with_auto_progress(mail_id)
        if not record:
            return None, f'mail({mail_id}) not found', ''

        is_fresh, stale_msg, stale_code = _validate_mail_record_freshness(record, expected_update_time)
        if not is_fresh:
            return None, stale_msg, stale_code

        is_admin = _is_admin(operator)
        cur_status = str(record.get('status', '')).strip()
        history = record.get('operationHistory', [])
        if not isinstance(history, list):
            history = []

        next_status = ''
        op_name = ''
        comment = ''

        if op_code == MAIL_REVIEW_OP_CODE:
            can_do, deny_msg = _can_review_mail(record, operator, is_admin)
            if not can_do:
                return None, deny_msg, ''
            next_status = MAIL_STATUS_PENDING_APPROVE
            need_notify_review = True
            op_name = 'review'
            comment = '提交审核'

        elif op_code == MAIL_PASS_OP_CODE:
            can_do, deny_msg = _can_pass_mail(record, is_admin)
            if not can_do:
                return None, deny_msg, ''

            dispatch_success, dispatch_err, dispatch_detail = MailDispatchImp.dispatch(operator, record)
            if not dispatch_success:
                logger.error('mail dispatch failed. mail_id=%s operator=%s err=%s detail=%s', mail_id, operator, dispatch_err, dispatch_detail)
                return None, f'game mail dispatch failed: {dispatch_err}', ''

            dispatch_detail = dispatch_detail if isinstance(dispatch_detail, dict) else {}
            dispatch_server_ids = dispatch_detail.get('success_server_ids', [])
            if not isinstance(dispatch_server_ids, list):
                dispatch_server_ids = []
            dispatch_server_ids = [int(item) for item in dispatch_server_ids if _safe_int(item, 0) > 0]

            dispatch_op_nuid = str(dispatch_detail.get('op_nuid', '') or '').strip()
            dispatch_op_nuid_by_server = dispatch_detail.get('op_nuid_by_server', {})
            if not isinstance(dispatch_op_nuid_by_server, dict):
                dispatch_op_nuid_by_server = {}

            if not dispatch_op_nuid and dispatch_op_nuid_by_server:
                dispatch_op_nuid = str(next(iter(dispatch_op_nuid_by_server.values()), '') or '').strip()

            send_dimension = str(record.get('sendDimension', 'server') or 'server').strip().lower()
            if send_dimension == 'role':
                next_status = MAIL_STATUS_IN_EFFECT
                comment = '审批通过，个人邮件立即生效'
            else:
                scheduled_dt = _parse_datetime_to_bj(record.get('scheduledTime'))
                now_dt = datetime.now(BEIJING_TZ)
                if scheduled_dt and scheduled_dt > now_dt:
                    next_status = MAIL_STATUS_PENDING_EFFECT
                    comment = '审批通过，进入待生效'
                else:
                    next_status = MAIL_STATUS_IN_EFFECT
                    comment = '审批通过，立即生效'
            op_name = 'pass'
            need_notify_passed = True

        elif op_code == MAIL_REJECT_OP_CODE:
            can_do, deny_msg = _can_reject_mail(record, is_admin)
            if not can_do:
                return None, deny_msg, ''
            next_status = MAIL_STATUS_PENDING_SUBMIT
            op_name = 'reject'
            comment = '审批驳回'

        elif op_code == MAIL_RECALL_OP_CODE:
            can_do, deny_msg, resolved_next_status, resolved_comment = _can_recall_mail(record, operator, is_admin)
            if not can_do:
                return None, deny_msg, ''

            if str(record.get('status', '')).strip() == MAIL_STATUS_PENDING_EFFECT:
                revoke_success, revoke_err, revoke_detail = MailDispatchImp.revoke(operator, record)
                if not revoke_success:
                    logger.error('mail revoke failed. mail_id=%s operator=%s err=%s detail=%s', mail_id, operator, revoke_err, revoke_detail)
                    return None, f'game mail revoke failed: {revoke_err}', ''

            next_status = resolved_next_status
            op_name = 'recall'
            comment = resolved_comment or '邮件撤回'

        else:
            return None, f'unsupported status op_code: {op_code}', ''

        updated_record = {
            **record,
            'status': next_status,
            'updateTime': now_str()
        }

        if op_code == MAIL_PASS_OP_CODE:
            if dispatch_server_ids:
                updated_record['dispatchServerIds'] = dispatch_server_ids
            if dispatch_op_nuid:
                updated_record['dispatchOpNUID'] = dispatch_op_nuid
            valid_dispatch_op_nuid_by_server = {}
            for server_id, op_nuid in dispatch_op_nuid_by_server.items():
                sid = _safe_int(server_id, 0)
                op_nuid_text = str(op_nuid or '').strip()
                if sid <= 0 or not op_nuid_text:
                    continue
                valid_dispatch_op_nuid_by_server[str(sid)] = op_nuid_text
            if valid_dispatch_op_nuid_by_server:
                updated_record['dispatchOpNUIDByServer'] = valid_dispatch_op_nuid_by_server

        if op_code == MAIL_RECALL_OP_CODE and cur_status == MAIL_STATUS_PENDING_EFFECT:
            updated_record.pop('dispatchServerIds', None)
            updated_record.pop('dispatchOpNUID', None)
            updated_record.pop('dispatchOpNUIDByServer', None)

        history.append(_build_operation_history(
            op_code,
            op_name,
            operator,
            cur_status,
            next_status,
            comment
        ))
        updated_record['operationHistory'] = history

        if not _save_mail_record(updated_record):
            return None, 'save status changed mail record failed', ''

    logger.info('mail status changed. mail_id=%s operator=%s op_code=%s from_status=%s to_status=%s', mail_id, operator, op_code, cur_status, next_status)

    if need_notify_review:
        notify_success, notify_err = KimRobot.remind_pass(_load_admin_whitelist(), mail_id)
        if not notify_success and notify_err:
            logger.warning('kim remind_pass failed. mail_id=%s operator=%s err=%s', mail_id, operator, notify_err)
    
    if need_notify_passed:
        notify_success, notify_err = KimRobot.remind_passed(mail_id, operator)
        if not notify_success and notify_err:
            logger.warning('kim remind_passed failed. mail_id=%s operator=%s creator=%s err=%s', mail_id, operator, notify_err)

    return updated_record, '', ''


def _build_error_response(message, status_code=400, code=''):
    response_body = {'message': message}
    if code:
        response_body['code'] = code
    return response_body, status_code


def _normalize_template_text(value):
    if value is None:
        return ''
    return str(value).strip()


def _normalize_template_datetime(value):
    text = _normalize_template_text(value)
    return text if text else ''


def _normalize_template_bool(value):
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()
    if text in ['1', 'true', 'yes', 'y', 'on']:
        return True
    if text in ['0', 'false', 'no', 'n', 'off']:
        return False
    return bool(value)


def _normalize_template_item(item, fallback_id):
    if not isinstance(item, dict):
        return None

    template_id = _safe_int(item.get('id'), 0)
    if template_id <= 0:
        template_id = fallback_id

    raw_valid_duration = item.get('validDuration', None)
    if raw_valid_duration in [None, '']:
        valid_duration = None
    else:
        valid_duration = _safe_int(raw_valid_duration, None)
        if valid_duration == 0:
            valid_duration = -1

    min_level = item.get('minLevel')
    if min_level in [None, '']:
        normalized_min_level = None
    else:
        normalized_min_level = _safe_int(min_level, None)

    send_dimension = _normalize_template_text(item.get('sendDimension', '')).lower()
    if send_dimension not in ['server', 'role']:
        send_dimension = ''

    recipient_type = _normalize_template_text(item.get('recipientType', '')).lower()
    if recipient_type not in ['server', 'role']:
        recipient_type = ''

    role_ids = _normalize_template_text(item.get('roleIds', ''))

    servers = item.get('servers', [])
    if not isinstance(servers, list):
        servers = []
    normalized_servers = []
    for server in servers:
        server_text = _normalize_template_text(server)
        if server_text:
            normalized_servers.append(server_text)

    rewards = item.get('rewards', [])
    if not isinstance(rewards, list):
        rewards = []

    normalized_rewards = []
    for reward in rewards:
        if not isinstance(reward, dict):
            continue
        item_id = _safe_int(reward.get('itemId'), 0)
        count = _safe_int(reward.get('count'), 0)
        if item_id <= 0 or count <= 0:
            continue
        normalized_rewards.append({
            'itemId': item_id,
            'count': count,
            'bind': bool(reward.get('bind', True))
        })

    return {
        'id': template_id,
        'name': _normalize_template_text(item.get('name', '')),
        'templateId': _normalize_template_text(item.get('templateId', '')),
        'taskName': _normalize_template_text(item.get('taskName', '')),
        'title': _normalize_template_text(item.get('title', '')),
        'content': _normalize_template_text(item.get('content', '')),
        'region': _normalize_template_text(item.get('region', '')),
        'channel': _normalize_template_text(item.get('channel', '')),
        'subChannel': _normalize_template_text(item.get('subChannel', '')),
        'sendDimension': send_dimension,
        'recipientType': recipient_type,
        'servers': normalized_servers,
        'roleIds': role_ids,
        'scheduledTime': _normalize_template_datetime(item.get('scheduledTime')),
        'expireTime': _normalize_template_datetime(item.get('expireTime')),
        'useScheduledAsReceiveTime': _normalize_template_bool(item.get('useScheduledAsReceiveTime', None)),
        'validDuration': valid_duration,
        'sender': _normalize_template_text(item.get('sender', '')),
        'minLevel': normalized_min_level,
        'createTimeCondition': _normalize_template_datetime(item.get('createTimeCondition')),
        'addToFav': _normalize_template_bool(item.get('addToFav', None)),
        'rewards': normalized_rewards
    }


def handle_get_mail_templates():
    try:
        templates = load_mail_templates_from_db()
    except Exception as err:
        logger.error('load mail templates failed. err=%s', err)
        return {'message': 'load templates failed'}, 500

    return {
        'result': {
            'templates': templates if isinstance(templates, list) else []
        }
    }, 200


def handle_save_mail_templates(username, payload):
    if not _is_admin(username):
        return {'message': 'no permission: admin only'}, 403

    templates = (payload or {}).get('templates', [])
    if not isinstance(templates, list):
        return {'message': 'templates must be an array'}, 400

    normalized_templates = []
    next_id = 1
    used_ids = set()

    for item in templates:
        normalized = _normalize_template_item(item, next_id)
        if not normalized:
            continue

        template_id = normalized['id']
        while template_id in used_ids or template_id <= 0:
            template_id += 1
        normalized['id'] = template_id
        used_ids.add(template_id)
        next_id = max(next_id, template_id + 1)
        normalized_templates.append(normalized)

    try:
        save_mail_templates_to_db(normalized_templates)
    except Exception as err:
        logger.error('save mail templates failed. user=%s err=%s', username, err)
        return {'message': 'save templates failed'}, 500

    logger.info('mail templates updated. user=%s count=%s', username, len(normalized_templates))
    return {
        'result': {
            'templates': normalized_templates
        }
    }, 200


def handle_select_mail(query_args):
    page = _safe_int(query_args.get('page', 1), 1)
    page_size = _safe_int(query_args.get('pageSize', 20), 20)
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 1000:
        page_size = 1000

    status_values = _parse_list_query_values(query_args, 'status')
    status_filter = ','.join(status_values)
    server_env_values = _parse_list_query_values(query_args, 'serverEnvType')
    if not server_env_values:
        server_env_values = _parse_list_query_values(query_args, 'serverEnvTypes')
    server_env_filter = ','.join(server_env_values)

    sort_field = str(query_args.get('sortField', query_args.get('sort_by', 'mail_id'))).strip() or 'mail_id'
    sort_order = str(query_args.get('sortOrder', query_args.get('sort_order', 'desc'))).strip() or 'desc'
    start = (page - 1) * page_size

    try:
        records, total = list_mail_records_from_db(
            status=status_filter,
            server_env_type=server_env_filter,
            skip=start,
            limit=page_size,
            sort_by=sort_field,
            sort_order=sort_order
        )
    except Exception as err:
        logger.error('select mail list from db failed. page=%s page_size=%s status=%s env=%s sort_field=%s sort_order=%s err=%s', page, page_size, status_filter, server_env_filter, sort_field, sort_order, err)
        return {'message': 'load mail list failed'}, 500

    page_records = []
    for record in records:
        if not isinstance(record, dict):
            continue

        updated_record, changed = _apply_auto_state_progress(record)
        if changed:
            _save_mail_record(updated_record)

        if status_values and str(updated_record.get('status', '')).strip() not in status_values:
            continue
        if server_env_values:
            normalized_record_env_values = _resolve_record_env_types(updated_record)
            if not normalized_record_env_values.intersection({item.lower() for item in server_env_values}):
                continue
        page_records.append(updated_record)

    return {
        'result': {
            'list': page_records,
            'total': total,
            'page': page,
            'pageSize': page_size
        }
    }, 200


def handle_mail_detail(query_args):
    mail_id = _safe_int(query_args.get('mail_id', query_args.get('mailId')), 0)
    if mail_id <= 0:
        return {'message': 'mail_id is required'}, 400

    with _mail_file_lock:
        record = _load_mail_record_with_auto_progress(mail_id)

    if not record:
        return {'message': f'mail({mail_id}) not found'}, 404

    return {
        'result': {
            'mail': record
        }
    }, 200


def handle_op_mail(username: str, payload: dict):
    op_code = payload.get('op_code')
    expected_update_time = _extract_expected_update_time(payload)
    try:
        op_code = int(op_code)
    except (TypeError, ValueError):
        return {'message': 'op_code is required and must be integer'}, 400

    if op_code == MAIL_CREATE_OP_CODE:
        data = payload.get('data', {})
        mail_record, err_msg = create_mail_record(username, data)
        if err_msg:
            return {'message': err_msg}, 400
        return {
            'result': {
                'mail_id': mail_record['mailId'],
                'mail': mail_record
            }
        }, 200

    if op_code == MAIL_EDIT_OP_CODE:
        mail_id = _extract_mail_id(payload)
        data = payload.get('data', {})
        mail_record, err_msg, err_code = edit_mail_record(username, mail_id, data, expected_update_time)
        if err_msg:
            if err_code == MAIL_STALE_VERSION_CODE:
                return _build_error_response(MAIL_STALE_VERSION_MESSAGE, 409, MAIL_STALE_VERSION_CODE)
            return _build_error_response(err_msg, 400, err_code)
        return {
            'result': {
                'mail_id': mail_record['mailId'],
                'mail': mail_record
            }
        }, 200

    if op_code == MAIL_DELETE_OP_CODE:
        mail_id = _extract_mail_id(payload)
        delete_result, err_msg, err_code = delete_mail_record(username, mail_id, expected_update_time)
        if err_msg:
            if err_code == MAIL_STALE_VERSION_CODE:
                return _build_error_response(MAIL_STALE_VERSION_MESSAGE, 409, MAIL_STALE_VERSION_CODE)
            return _build_error_response(err_msg, 400, err_code)
        return {
            'result': delete_result
        }, 200

    if op_code in [MAIL_REVIEW_OP_CODE, MAIL_PASS_OP_CODE, MAIL_RECALL_OP_CODE, MAIL_REJECT_OP_CODE]:
        mail_id = _extract_mail_id(payload)
        mail_record, err_msg, err_code = change_mail_status(username, mail_id, op_code, expected_update_time)
        if err_msg:
            if err_code == MAIL_STALE_VERSION_CODE:
                return _build_error_response(MAIL_STALE_VERSION_MESSAGE, 409, MAIL_STALE_VERSION_CODE)
            return _build_error_response(err_msg, 400, err_code)
        return {
            'result': {
                'mail_id': mail_record['mailId'],
                'mail': mail_record
            }
        }, 200

    return {
        'message': f'Unsupported op_code: {op_code}'
    }, 400


def _normalize_environment_type(raw_value):
    raw = str(raw_value or '').strip().lower()
    if raw in ['1', 'debug', 'debugging', 'test']:
        return EnvironmentTypes.DEBUGGING
    return EnvironmentTypes.ONLINE


def _normalize_zone_server_data(kdip_data):
    if not isinstance(kdip_data, list):
        return []

    zones = []
    for zone in kdip_data:
        if not isinstance(zone, dict):
            continue
        zone_id = zone.get('zoneId', zone.get('id'))
        zone_name = zone.get('zoneName', zone.get('name', f'zone-{zone_id}'))
        server_infos = zone.get('serverInfos', [])
        normalized_servers = []
        for server in (server_infos if isinstance(server_infos, list) else []):
            if not isinstance(server, dict):
                continue
            server_value = str(server.get('serverId', server.get('id', ''))).strip()
            if not server_value:
                continue
            normalized_servers.append({
                'value': server_value,
                'label': str(server.get('name', server_value)).strip() or server_value
            })

        zones.append({
            'value': str(zone_id),
            'label': str(zone_name),
            'servers': normalized_servers
        })
    return zones


def _env_text(environment_type):
    return '正式服' if environment_type == EnvironmentTypes.ONLINE else '测试服'


def _normalize_zone_server_data_with_env(kdip_data, environment_type):
    base_zones = _normalize_zone_server_data(kdip_data)
    env_value = 'online' if environment_type == EnvironmentTypes.ONLINE else 'debugging'
    env_label = _env_text(environment_type)

    zones = []
    for zone in base_zones:
        zone_value = str(zone.get('value', '')).strip()
        zone_label = str(zone.get('label', zone_value)).strip() or zone_value
        zone_servers = []
        for server in zone.get('servers', []):
            server_id = str(server.get('value', '')).strip()
            server_label = str(server.get('label', server_id)).strip() or server_id
            if not server_id:
                continue
            server_key = f'{env_value}|{server_id}'
            zone_servers.append({
                'value': server_key,
                'label': f'[{env_label}] {server_label}',
                'serverId': server_id,
                'environmentType': env_value,
                'environmentLabel': env_label
            })

        zones.append({
            'value': f'{env_value}|{zone_value}' if zone_value else env_value,
            'zoneId': zone_value,
            'label': f'[{env_label}] {zone_label}',
            'zoneName': zone_label,
            'environmentType': env_value,
            'environmentLabel': env_label,
            'servers': zone_servers
        })
    return zones


def _normalize_channel_data(kdip_data):
    channel_options = []

    if isinstance(kdip_data, dict):
        for channel_name, _sub_channels in kdip_data.items():
            channel_value = str(channel_name).strip()
            if not channel_value:
                continue
            channel_options.append({'value': channel_value, 'label': channel_value})
        return channel_options

    if isinstance(kdip_data, list):
        for item in kdip_data:
            if isinstance(item, dict):
                channel_value = str(item.get('value', item.get('code', item.get('name', '')))).strip()
                channel_label = str(item.get('name', channel_value)).strip() or channel_value
            else:
                channel_value = str(item).strip()
                channel_label = channel_value
            if not channel_value:
                continue
            channel_options.append({'value': channel_value, 'label': channel_label})
        return channel_options

    return channel_options


def _normalize_platform_data(kdip_data, channels):
    platform_items = []
    if isinstance(kdip_data, list):
        for item in kdip_data:
            if isinstance(item, dict):
                platform_value = str(item.get('value', item.get('code', item.get('name', '')))).strip()
                platform_label = str(item.get('name', platform_value)).strip() or platform_value
            else:
                platform_value = str(item).strip()
                platform_label = platform_value
            if not platform_value:
                continue
            platform_items.append({'value': platform_value, 'label': platform_label})

    sub_channel_options = []
    if not channels:
        return platform_items, sub_channel_options

    for channel in channels:
        channel_value = str(channel.get('value', '')).strip()
        if not channel_value:
            continue
        for platform in platform_items:
            sub_channel_options.append({
                'value': platform['value'],
                'label': platform['label'],
                'channel': channel_value
            })

    return platform_items, sub_channel_options


def _normalize_channel_map_item(primary_channel, item):
    primary = str(primary_channel or '').strip()
    if not primary:
        return None

    if isinstance(item, str):
        market_channel = item.strip()
        if not market_channel:
            return None
        return {
            'primary': primary,
            'value': market_channel,
            'label': market_channel
        }

    if not isinstance(item, dict):
        return None

    market_channel = str(item.get('value', item.get('marketChannel', item.get('MarketChannel', '')))).strip()
    if not market_channel:
        return None
    remark = str(item.get('remark', item.get('备注', ''))).strip()
    label = f'{market_channel}-{remark}' if remark else market_channel
    return {
        'primary': primary,
        'value': market_channel,
        'label': label
    }


def _build_channel_mapping_from_config(file_path):
    if not file_path:
        logger.warning('channel map config path is empty')
        return {}, 'CHANNEL_MAP_CONFIG_FILE is empty'
    if not os.path.exists(file_path):
        logger.warning('channel map config file not found. file=%s', file_path)
        return {}, f'channel map config not found: {file_path}'

    try:
        with open(file_path, 'r', encoding='utf-8') as fp:
            raw_config = json.load(fp)
    except (OSError, json.JSONDecodeError) as err:
        logger.warning('load channel map config failed. file=%s err=%s', file_path, err)
        return {}, f'load channel map config failed: {err}'

    try:
        mapping = {}
        existed = set()

        source = raw_config.get('channelMap', raw_config) if isinstance(raw_config, dict) else raw_config
        if isinstance(source, dict):
            for primary_channel, mapped_items in source.items():
                item_list = mapped_items if isinstance(mapped_items, list) else [mapped_items]
                for item in item_list:
                    normalized = _normalize_channel_map_item(primary_channel, item)
                    if not normalized:
                        continue
                    uniq_key = f"{normalized['primary']}|{normalized['value']}"
                    if uniq_key in existed:
                        continue
                    existed.add(uniq_key)
                    mapping.setdefault(normalized['primary'], []).append({
                        'value': normalized['value'],
                        'label': normalized['label']
                    })
        elif isinstance(source, list):
            for row in source:
                if not isinstance(row, dict):
                    continue
                primary_channel = str(row.get('primaryChannel', row.get('一级渠道', row.get('channel', '')))).strip()
                normalized = _normalize_channel_map_item(primary_channel, row)
                if not normalized:
                    continue
                uniq_key = f"{normalized['primary']}|{normalized['value']}"
                if uniq_key in existed:
                    continue
                existed.add(uniq_key)
                mapping.setdefault(normalized['primary'], []).append({
                    'value': normalized['value'],
                    'label': normalized['label']
                })
        else:
            logger.warning('channel map config format invalid. file=%s', file_path)
            return {}, 'channel map config format invalid'

        return mapping, ''
    except Exception as err:
        logger.exception('parse channel map config failed. file=%s err=%s', file_path, err)
        return {}, f'parse channel map config failed: {err}'


def _load_channel_mapping_cached():
    file_path = config.CHANNEL_MAP_CONFIG_FILE
    try:
        mtime = int(os.path.getmtime(file_path)) if file_path and os.path.exists(file_path) else 0
    except OSError:
        mtime = 0

    if (
        _channel_mapping_cache['map'] and
        _channel_mapping_cache['file'] == file_path and
        _channel_mapping_cache['mtime'] == mtime
    ):
        return _channel_mapping_cache['map'], ''

    mapping, err = _build_channel_mapping_from_config(file_path)
    if not err:
        _channel_mapping_cache['file'] = file_path
        _channel_mapping_cache['mtime'] = mtime
        _channel_mapping_cache['map'] = mapping
        logger.info('channel map cache refreshed. file=%s channels=%s', file_path, len(mapping))
    else:
        logger.warning('channel map cache refresh failed. file=%s err=%s', file_path, err)
    return mapping, err


def _build_sub_channels_by_primary_channel(channels):
    mapping, err = _load_channel_mapping_cached()
    if err:
        return [], err

    sub_channels = []
    existed = set()

    for channel in channels:
        channel_value = str(channel.get('value', '')).strip()
        if not channel_value:
            continue
        mapped_list = mapping.get(channel_value, [])
        for item in mapped_list:
            value = str(item.get('value', '')).strip()
            label = str(item.get('label', value)).strip() or value
            uniq = f'{channel_value}|{value}'
            if not value or uniq in existed:
                continue
            existed.add(uniq)
            sub_channels.append({
                'channel': channel_value,
                'value': value,
                'label': label
            })

    return sub_channels, ''


def _merge_unique_options(*option_lists):
    merged = []
    exists = set()
    for option_list in option_lists:
        if not isinstance(option_list, list):
            continue
        for item in option_list:
            if not isinstance(item, dict):
                continue
            value = str(item.get('value', '')).strip()
            label = str(item.get('label', value)).strip() or value
            if not value or value in exists:
                continue
            exists.add(value)
            merged.append({'value': value, 'label': label})
    return merged


def _merge_sub_channels(*option_lists):
    merged = []
    exists = set()
    for option_list in option_lists:
        if not isinstance(option_list, list):
            continue
        for item in option_list:
            if not isinstance(item, dict):
                continue
            channel = str(item.get('channel', '')).strip()
            value = str(item.get('value', '')).strip()
            label = str(item.get('label', value)).strip() or value
            uniq_key = f'{channel}|{value}'
            if not channel or not value or uniq_key in exists:
                continue
            exists.add(uniq_key)
            merged.append({'channel': channel, 'value': value, 'label': label})
    return merged


def handle_kdip_options(query_args):
    env_list = [EnvironmentTypes.ONLINE, EnvironmentTypes.DEBUGGING]
    all_zones = []
    all_channels = []
    all_platforms = []
    all_sub_channels = []
    failed_envs = []

    for environment_type in env_list:
        zone_server_raw = KdipServer.get_zone_server_list(environment_type)
        channel_raw = KdipServer.get_channel_list(environment_type)

        has_failed = (
            zone_server_raw == KdipCodeStatusTypes.FAILED or
            channel_raw == KdipCodeStatusTypes.FAILED
        )
        if has_failed:
            logger.warning('kdip options pull failed. env=%s zone_failed=%s channel_failed=%s', _env_text(environment_type), zone_server_raw == KdipCodeStatusTypes.FAILED, channel_raw == KdipCodeStatusTypes.FAILED)
            failed_envs.append(_env_text(environment_type))
            continue

        zones = _normalize_zone_server_data_with_env(zone_server_raw, environment_type)
        channels = _normalize_channel_data(channel_raw)
        sub_channels, sub_err = _build_sub_channels_by_primary_channel(channels)
        if sub_err:
            logger.warning('build sub channels by channel map failed. env=%s err=%s', _env_text(environment_type), sub_err)
            failed_envs.append(f'{_env_text(environment_type)}-二级渠道映射')

        all_zones.extend(zones)
        all_channels = _merge_unique_options(all_channels, channels)
        all_platforms = _merge_unique_options(all_platforms, [])
        all_sub_channels = _merge_sub_channels(all_sub_channels, sub_channels)

    if not all_zones and not all_channels and not all_platforms:
        logger.error('kdip options request failed for all environments')
        return {'message': 'KDIP options request failed for both online/debugging environments'}, 502

    result = {
        'zones': all_zones,
        'channels': all_channels,
        'platforms': all_platforms,
        'subChannels': all_sub_channels
    }
    if failed_envs:
        result['warnings'] = [f"以下环境拉取失败: {','.join(failed_envs)}"]
        logger.warning('kdip options partial failure. failed_envs=%s', ','.join(failed_envs))

    logger.info('kdip options loaded. zones=%s channels=%s sub_channels=%s', len(all_zones), len(all_channels), len(all_sub_channels))

    return {'result': result}, 200
