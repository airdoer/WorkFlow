import base64
import hashlib
import hmac
import json
import logging
import random
import re
import time
from datetime import datetime

import config
from Implement.kdipServerImpl.kdipServerImp import KdipServer, KdipCodeStatusTypes, KdipPostRoute, EnvironmentTypes


GM_CMD_SERVER_MAIL_SEND = 'gamedesigner-server-mail-send'
GM_CMD_PERSON_MAIL_SEND = 'gamedesigner-person-mail-send'
GM_CMD_REVOKE_MAIL_BY_OP_NUID = 'gamedesigner-revoke-pending-server-mail-opNUID'
logger = logging.getLogger(__name__)


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_iso_to_timestamp(value):
    text = str(value or '').strip()
    if not text:
        return None

    text = text.replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None

    return int(dt.timestamp())

def _extract_add_to_fav(record):
    value = record.get('add_to_fav', None)
    if value is None:
        value = record.get('addToFav', 0)

    if isinstance(value, bool):
        return 1 if value else 0

    if isinstance(value, (int, float)):
        return 1 if int(value) == 1 else 0

    text = str(value or '').strip().lower()
    if text in ('1', 'true', 'yes', 'y'):
        return 1
    return 0

def _extract_env(record):
    env_values = record.get('serverEnvTypes', [])
    if isinstance(env_values, list):
        for item in env_values:
            env = str(item or '').strip().lower()
            if env == 'online':
                return EnvironmentTypes.ONLINE
            if env == 'debugging':
                return EnvironmentTypes.DEBUGGING

    region = str(record.get('region', '')).strip().lower()
    if region == 'online' or region.startswith('online|'):
        return EnvironmentTypes.ONLINE
    if region == 'debugging' or region.startswith('debugging|'):
        return EnvironmentTypes.DEBUGGING

    return EnvironmentTypes.ONLINE


def _extract_zone_id(record):
    region = str(record.get('region', '')).strip()
    if '|' in region:
        parts = region.split('|', 1)
        return str(parts[1]).strip()
    return ''


def _normalize_server_ids(record):
    ids = []
    servers = record.get('servers', [])
    if isinstance(servers, list):
        for item in servers:
            sid = _safe_int(item, 0)
            if sid > 0 and sid not in ids:
                ids.append(sid)
    elif servers:
        for item in str(servers).split(','):
            sid = _safe_int(item.strip(), 0)
            if sid > 0 and sid not in ids:
                ids.append(sid)
    return ids


def _resolve_all_servers_by_zone(environment_type, zone_id):
    if not zone_id:
        return []

    zone_data = KdipServer.get_zone_server_list(environment_type)
    if not isinstance(zone_data, list):
        return []

    target = str(zone_id).strip()
    result = []
    for zone in zone_data:
        if not isinstance(zone, dict):
            continue
        cur_zone_id = str(zone.get('zoneId', zone.get('id', ''))).strip()
        if cur_zone_id != target:
            continue
        for server in zone.get('serverInfos', []):
            if not isinstance(server, dict):
                continue
            sid = _safe_int(server.get('serverId', server.get('id')), 0)
            if sid > 0 and sid not in result:
                result.append(sid)
        break

    return result


def _normalize_role_ids(role_ids):
    text = str(role_ids or '').strip()
    if not text:
        return []
    values = re.split(r'[\s,，\n\r]+', text)
    result = []
    for item in values:
        value = str(item).strip()
        if value and value not in result:
            result.append(value)
    return result


def _normalize_attaches(record):
    rewards = record.get('rewards', [])
    if not isinstance(rewards, list):
        return []

    attaches = []
    for reward in rewards:
        if not isinstance(reward, dict):
            continue
        item_id = _safe_int(reward.get('itemId'), 0)
        amount = _safe_int(reward.get('count'), 0)
        if item_id <= 0 or amount <= 0:
            continue
        bind_value = reward.get('bind', True)
        is_bound = 1 if bool(bind_value) else 0
        attaches.append({
            'item_id': str(item_id),
            'amount': str(amount),
            'is_bound': int(is_bound)
        })
    return attaches


def _filter_dev_allowed_servers(server_ids):
    normalized = []
    for sid in server_ids:
        value = _safe_int(sid, 0)
        if value > 0 and value not in normalized:
            normalized.append(value)

    if not config.MAIL_GAME_SEND_DEV_GUARD_ENABLED:
        return normalized, []

    allowed_ids = [int(item) for item in (config.MAIL_GAME_SEND_ALLOWED_SERVER_IDS or []) if _safe_int(item, 0) > 0]
    if not allowed_ids:
        return [], normalized

    allowed_set = set(allowed_ids)
    accepted = [sid for sid in normalized if sid in allowed_set]
    rejected = [sid for sid in normalized if sid not in allowed_set]
    return accepted, rejected


def _build_server_mail_cmd(record, target_server_id):
    payload = {
        'server_list': [int(target_server_id)],
        'title': str(record.get('title', '')).strip(),
        'content': str(record.get('content', '')).strip(),
        'sender': str(record.get('sender', '')).strip(),
        'attaches': _normalize_attaches(record),
        'add_to_fav': _extract_add_to_fav(record),
        'expire_days': '',
        'earliest_send_time': '',
        'latest_send_time': '',
        'lv_limit': '',
        'show_time_type': '',
        'role_create_time_limit': '',
        'package_channel': []
    }

    valid_duration = _safe_int(record.get('validDuration'), -1)
    if valid_duration > 0:
        payload['expire_days'] = str(valid_duration)

    earliest = _parse_iso_to_timestamp(record.get('scheduledTime'))
    if earliest is None:
        earliest = int(time.time())
    payload['earliest_send_time'] = str(earliest)

    latest = _parse_iso_to_timestamp(record.get('expireTime'))
    if latest:
        payload['latest_send_time'] = str(latest)

    min_level = _safe_int(record.get('minLevel'), 0)
    if min_level > 0:
        payload['lv_limit'] = str(min_level)

    payload['show_time_type'] = '1' if bool(record.get('useScheduledAsReceiveTime')) else '2'

    role_create_limit = _parse_iso_to_timestamp(record.get('createTimeCondition'))
    if role_create_limit:
        payload['role_create_time_limit'] = str(role_create_limit)

    return payload


def _build_role_mail_cmd(record, target_server_id):
    avatar_ids = _normalize_role_ids(record.get('roleIds'))
    if not avatar_ids:
        return None, 'avatar_short_uid_list is required'

    payload = {
        'server_id': str(target_server_id),
        'avatar_short_uid_list': avatar_ids,
        'title': str(record.get('title', '')).strip(),
        'content': str(record.get('content', '')).strip(),
        'sender': str(record.get('sender', '')).strip(),
        'attaches': _normalize_attaches(record),
        'add_to_fav': _extract_add_to_fav(record),
        'expire_days': ''
    }

    valid_duration = _safe_int(record.get('validDuration'), -1)
    if valid_duration > 0:
        payload['expire_days'] = str(valid_duration)

    return payload, ''


def _build_seq_id(prefix='MAIL_SEND'):
    timestamp = int(time.time() * 1000)
    random_part = str(random.randint(1, 999999)).zfill(6)
    return f'GM_EXTEND_CMD_{prefix}_{timestamp}_{random_part}'


def _build_sign(data_obj):
    body = json.dumps(data_obj, separators=(',', ':'), ensure_ascii=False)
    secret = str(config.KDIP_APP_SECRET or '').encode('utf-8')
    body_bytes = body.encode('utf-8')
    signature = base64.b64encode(hmac.new(secret, body_bytes, hashlib.sha256).digest())
    return signature.decode('utf-8')


def _post_extend_cmd(user_name, environment_type, payload):
    headers = {
        'seqId': _build_seq_id(),
        'sign': _build_sign(payload)
    }
    body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
    logger.info(
        'mail dispatch request. user=%s env=%s server_id=%s cmd_key=%s seq_id=%s payload=%s',
        user_name,
        environment_type,
        payload.get('serverId'),
        ((payload.get('cmdParam') or {}).get('cmd_key')),
        headers.get('seqId'),
        body
    )
    result = KdipServer.send_extend_cmd(user_name, environment_type, body, headers)
    logger.info(
        'mail dispatch response. user=%s env=%s server_id=%s cmd_key=%s success=%s result=%s',
        user_name,
        environment_type,
        payload.get('serverId'),
        ((payload.get('cmdParam') or {}).get('cmd_key')),
        result != KdipCodeStatusTypes.FAILED,
        result
    )
    return result != KdipCodeStatusTypes.FAILED, result


def _extract_op_nuid(raw_result):
    if raw_result in [None, '']:
        return ''

    if isinstance(raw_result, str):
        text = raw_result.strip()
        if not text:
            return ''
        try:
            parsed = json.loads(text)
        except Exception:
            return ''
        return _extract_op_nuid(parsed)

    if isinstance(raw_result, list):
        for item in raw_result:
            value = _extract_op_nuid(item)
            if value:
                return value
        return ''

    if isinstance(raw_result, dict):
        for key in ['opNUID', 'opNuid', 'op_nuid', 'opUuid', 'op_uuid', 'uuid']:
            value = raw_result.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()

        for key in ['data', 'result', 'payload', 'ret', 'response']:
            if key in raw_result:
                value = _extract_op_nuid(raw_result.get(key))
                if value:
                    return value

    return ''


def _group_servers_by_op_nuid(op_nuid_by_server):
    grouped = {}
    if not isinstance(op_nuid_by_server, dict):
        return grouped

    for server_id, op_nuid in op_nuid_by_server.items():
        sid = _safe_int(server_id, 0)
        op_nuid_text = str(op_nuid or '').strip()
        if sid <= 0 or not op_nuid_text:
            continue
        grouped.setdefault(op_nuid_text, [])
        if sid not in grouped[op_nuid_text]:
            grouped[op_nuid_text].append(sid)
    return grouped


def _build_revoke_mail_cmd(op_nuid, server_ids):
    return {
        'opNUID': str(op_nuid or '').strip(),
        'server_list': [int(item) for item in server_ids if _safe_int(item, 0) > 0]
    }


class MailDispatchImp:
    @staticmethod
    def dispatch(user_name, record):
        if not isinstance(record, dict):
            logger.error('mail dispatch aborted: invalid record type. user=%s record_type=%s', user_name, type(record).__name__)
            return False, 'mail record is invalid', {}

        mail_id = _safe_int(record.get('mailId', record.get('id')), 0)
        send_dimension = str(record.get('sendDimension') or 'server').strip().lower()
        environment_type = _extract_env(record)
        zone_id = _extract_zone_id(record)
        logger.info(
            'mail dispatch start. user=%s mail_id=%s dimension=%s env=%s zone_id=%s title_len=%s rewards=%s',
            user_name,
            mail_id,
            send_dimension,
            environment_type,
            zone_id,
            len(str(record.get('title', '') or '')),
            len(record.get('rewards', []) or []) if isinstance(record.get('rewards', []), list) else 0
        )

        server_ids = _normalize_server_ids(record)
        logger.info('mail dispatch target parsed. mail_id=%s dimension=%s explicit_server_ids=%s', mail_id, send_dimension, server_ids)
        if not server_ids and send_dimension == 'server':
            server_ids = _resolve_all_servers_by_zone(environment_type, zone_id)
            logger.info('mail dispatch target resolved by zone. mail_id=%s zone_id=%s server_ids=%s', mail_id, zone_id, server_ids)

        if send_dimension == 'role' and len(server_ids) > 1:
            logger.error('mail dispatch validation failed. mail_id=%s reason=role_send_requires_single_server server_ids=%s', mail_id, server_ids)
            return False, 'role send requires exactly one server', {'server_ids': server_ids}

        accepted_ids, rejected_ids = _filter_dev_allowed_servers(server_ids)
        logger.info(
            'mail dispatch guard check. mail_id=%s guard_enabled=%s input_server_ids=%s accepted=%s rejected=%s',
            mail_id,
            config.MAIL_GAME_SEND_DEV_GUARD_ENABLED,
            server_ids,
            accepted_ids,
            rejected_ids
        )
        if rejected_ids:
            logger.warning('mail dispatch blocked by dev guard. mail_id=%s rejected_server_ids=%s', mail_id, rejected_ids)
            return False, f'dev guard blocked server ids: {rejected_ids}', {
                'accepted_server_ids': accepted_ids,
                'rejected_server_ids': rejected_ids
            }

        if not accepted_ids:
            logger.error('mail dispatch validation failed. mail_id=%s reason=no_valid_target_server server_ids=%s', mail_id, server_ids)
            return False, 'no valid target server ids', {'server_ids': server_ids}

        success_ids = []
        failed_items = []
        op_nuid_by_server = {}

        if send_dimension == 'role':
            target_server_id = accepted_ids[0]
            cmd_param, err = _build_role_mail_cmd(record, target_server_id)
            if err:
                logger.error('mail dispatch role payload build failed. mail_id=%s server_id=%s err=%s', mail_id, target_server_id, err)
                return False, err, {'server_ids': accepted_ids}

            payload = {
                'serverId': target_server_id,
                'cmdParam': {
                    'cmd_key': GM_CMD_PERSON_MAIL_SEND,
                    'cmd_param': cmd_param
                }
            }
            if zone_id:
                payload['zoneId'] = zone_id

            ok, raw_result = _post_extend_cmd(user_name, environment_type, payload)
            if ok:
                success_ids.append(target_server_id)
                op_nuid = _extract_op_nuid(raw_result)
                if op_nuid:
                    op_nuid_by_server[str(target_server_id)] = op_nuid
                logger.info('mail dispatch role send success. mail_id=%s server_id=%s', mail_id, target_server_id)
            else:
                failed_items.append({'server_id': target_server_id, 'result': raw_result})
                logger.error('mail dispatch role send failed. mail_id=%s server_id=%s raw_result=%s', mail_id, target_server_id, raw_result)

        else:
            for sid in accepted_ids:
                cmd_param = _build_server_mail_cmd(record, sid)
                payload = {
                    'serverId': sid,
                    'cmdParam': {
                        'cmd_key': GM_CMD_SERVER_MAIL_SEND,
                        'cmd_param': cmd_param
                    }
                }
                if zone_id:
                    payload['zoneId'] = zone_id

                ok, raw_result = _post_extend_cmd(user_name, environment_type, payload)
                if ok:
                    success_ids.append(sid)
                    op_nuid = _extract_op_nuid(raw_result)
                    if op_nuid:
                        op_nuid_by_server[str(sid)] = op_nuid
                    logger.info('mail dispatch server send success. mail_id=%s server_id=%s', mail_id, sid)
                else:
                    failed_items.append({'server_id': sid, 'result': raw_result})
                    logger.error('mail dispatch server send failed. mail_id=%s server_id=%s raw_result=%s', mail_id, sid, raw_result)

        if failed_items:
            logger.error(
                'mail dispatch finished with failures. mail_id=%s success_server_ids=%s failed_server_ids=%s',
                mail_id,
                success_ids,
                [item.get('server_id') for item in failed_items]
            )
            return False, f'send failed on servers: {[item.get("server_id") for item in failed_items]}', {
                'success_server_ids': success_ids,
                'failed_items': failed_items
            }

        logger.info('mail dispatch finished success. mail_id=%s success_server_ids=%s dimension=%s env=%s', mail_id, success_ids, send_dimension, environment_type)
        return True, '', {
            'success_server_ids': success_ids,
            'op_nuid_by_server': op_nuid_by_server,
            'op_nuid': next(iter(op_nuid_by_server.values()), ''),
            'send_dimension': send_dimension,
            'environment_type': environment_type
        }

    @staticmethod
    def revoke(user_name, record):
        if not isinstance(record, dict):
            return False, 'mail record is invalid', {}

        environment_type = _extract_env(record)
        zone_id = _extract_zone_id(record)
        mail_id = _safe_int(record.get('mailId', record.get('id')), 0)

        grouped = _group_servers_by_op_nuid(record.get('dispatchOpNUIDByServer', {}))
        if not grouped:
            op_nuid = str(record.get('dispatchOpNUID', '')).strip()
            server_ids = record.get('dispatchServerIds', [])
            if not isinstance(server_ids, list) or not server_ids:
                server_ids = _normalize_server_ids(record)
            if op_nuid and server_ids:
                grouped = {op_nuid: [int(item) for item in server_ids if _safe_int(item, 0) > 0]}

        if not grouped:
            return False, 'no opNUID/server_list found for revoke', {}

        failed_items = []
        success_items = []
        for op_nuid, server_ids in grouped.items():
            cmd_param = _build_revoke_mail_cmd(op_nuid, server_ids)
            if not cmd_param['opNUID'] or not cmd_param['server_list']:
                failed_items.append({'opNUID': op_nuid, 'server_ids': server_ids, 'result': 'invalid revoke params'})
                continue

            payload = {
                'serverId': int(cmd_param['server_list'][0]),
                'cmdParam': {
                    'cmd_key': GM_CMD_REVOKE_MAIL_BY_OP_NUID,
                    'cmd_param': cmd_param
                }
            }
            if zone_id:
                payload['zoneId'] = zone_id

            ok, raw_result = _post_extend_cmd(user_name, environment_type, payload)
            if ok:
                success_items.append({'opNUID': op_nuid, 'server_ids': cmd_param['server_list']})
                logger.info('mail revoke success. mail_id=%s opNUID=%s server_ids=%s', mail_id, op_nuid, cmd_param['server_list'])
            else:
                failed_items.append({'opNUID': op_nuid, 'server_ids': cmd_param['server_list'], 'result': raw_result})
                logger.error('mail revoke failed. mail_id=%s opNUID=%s server_ids=%s raw_result=%s', mail_id, op_nuid, cmd_param['server_list'], raw_result)

        if failed_items:
            return False, 'revoke failed on part of servers', {
                'success_items': success_items,
                'failed_items': failed_items
            }

        return True, '', {
            'success_items': success_items
        }
