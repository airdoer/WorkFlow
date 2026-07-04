import json
import os
from typing import Union

import requests

import config
from managers.timeMgr import TimeMgr


class EnvironmentTypes:
    DEBUGGING = 1
    ONLINE = 2


class KdipCodeStatusTypes:
    SUCCESS = 0
    FAILED = 1


class KdipConfigArgs:
    KDIP_ONLINE_DOMAIN = config.KDIP_ONLINE_DOMAIN
    KDIP_DEBUGGING_DOMAIN = config.KDIP_DEBUGGING_DOMAIN
    APP_ID = config.KDIP_APP_ID
    APP_SECRETE = config.KDIP_APP_SECRET
    GRANT_TYPE = config.KDIP_GRANT_TYPE
    SCOPE = config.KDIP_SCOPE
    GET_HEADERS = {'app-id': APP_ID, 'Content-Type': 'application/json; charset=utf-8'}
    POST_HEADERS = {'app-id': APP_ID, 'Content-Type': 'application/json; charset=utf-8', 'user-name': ''}


class KdipGetRoute:
    CHANNEL_LIST = '/{appId}/api/gm/admin/open/channels'
    SERVER_LIST = '/{appId}/api/gm/admin/open/server-infos'
    PLATFORM_LIST = '/{appId}/api/gm/admin/open/platforms'


class KdipPostRoute:
    EXTEND_CMD = '/{appId}/api/gm/kdip/open/extend-cmd'


class KdipServer:
    access_token_file = config.KDIP_ACCESS_TOKEN_FILE
    access_token = ''
    inited = False

    @staticmethod
    def _log(level: str, msg: str):
        try:
            from appImp import app
            logger = app.logger
            if level == 'error':
                logger.error(msg)
            elif level == 'warning':
                logger.warning(msg)
            else:
                logger.info(msg)
        except Exception:
            pass

    @staticmethod
    def _has_kdip_credential():
        return bool(KdipConfigArgs.APP_ID and KdipConfigArgs.APP_SECRETE)

    @staticmethod
    def _resolve_domain(environment_type):
        return (KdipConfigArgs.KDIP_ONLINE_DOMAIN if environment_type == EnvironmentTypes.ONLINE
                else KdipConfigArgs.KDIP_DEBUGGING_DOMAIN)

    @staticmethod
    def init_schedule():
        if KdipServer.inited:
            return

        KdipServer.load_access_token()

        if not config.KDIP_ENABLE:
            KdipServer._log('info', 'KDIP disabled by config')
            KdipServer.inited = True
            return

        if not KdipServer._has_kdip_credential():
            KdipServer._log('warning', 'KDIP enabled but KDIP_APP_ID / KDIP_APP_SECRET is empty')
            KdipServer.inited = True
            return

        if not KdipServer.access_token:
            KdipServer.get_access_token_once()

        interval_info = {
            'type': 'interval',
            'hour': max(1, int(config.KDIP_ACCESS_TOKEN_REFRESH_HOURS))
        }
        TimeMgr.add_schedule_interval(interval_info, KdipServer.get_access_token_once, 'kdip_access_token_refresh')
        KdipServer._log('info', 'KDIP schedule initialized')
        KdipServer.inited = True

    @staticmethod
    def load_access_token():
        token_file = KdipServer.access_token_file
        if not os.path.exists(token_file):
            KdipServer.access_token = ''
            return

        try:
            with open(token_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
            KdipServer.access_token = str((data or {}).get('access_token', '')).strip()
        except (OSError, json.JSONDecodeError):
            KdipServer.access_token = ''

    @staticmethod
    def save_access_token():
        token_file = KdipServer.access_token_file
        token_dir = os.path.dirname(token_file)
        if token_dir:
            os.makedirs(token_dir, exist_ok=True)
        with open(token_file, 'w', encoding='utf-8') as file:
            json.dump({'access_token': KdipServer.access_token}, file, ensure_ascii=False)

    @staticmethod
    def kdip_get(route, environment_type: EnvironmentTypes, need_access_token=False, headers=None):
        if not KdipServer._has_kdip_credential():
            return KdipCodeStatusTypes.FAILED

        headers = headers or {}
        url = KdipServer._resolve_domain(environment_type) + route.format(appId=KdipConfigArgs.APP_ID)
        headers.update(KdipConfigArgs.GET_HEADERS.copy())
        if need_access_token:
            headers['access-token'] = KdipServer.access_token

        try:
            res = requests.get(url, headers=headers, timeout=config.KDIP_REQUEST_TIMEOUT)
            res.raise_for_status()
            response_json = res.json()
            code = response_json.get('code')
            data = response_json.get('data')
            if code != KdipCodeStatusTypes.SUCCESS or data is None:
                if 'access-token' in str(response_json.get('msg', '')).lower():
                    KdipServer.get_access_token_once()
                    return KdipServer.kdip_get(route, environment_type, need_access_token=True)
                KdipServer._log('error', f'KdipServer kdip_get failed: {response_json}')
                return KdipCodeStatusTypes.FAILED
            return data
        except requests.exceptions.RequestException as http_error:
            KdipServer._log('error', f'KdipServer kdip_get failed: {http_error}')
            return KdipCodeStatusTypes.FAILED

    @staticmethod
    def kdip_post(route, user_name, environment_type: EnvironmentTypes, data: Union[str, dict], headers=None,
                  need_access_token=False):
        if not KdipServer._has_kdip_credential():
            return KdipCodeStatusTypes.FAILED

        headers = headers or {}
        url = KdipServer._resolve_domain(environment_type) + route.format(appId=KdipConfigArgs.APP_ID)
        headers.update(KdipConfigArgs.POST_HEADERS.copy())
        headers['user-name'] = user_name
        if need_access_token:
            headers['access-token'] = KdipServer.access_token

        try:
            res = requests.post(url, headers=headers, data=data, timeout=config.KDIP_REQUEST_TIMEOUT)
            res.raise_for_status()
            response_json = res.json()
            code = response_json.get('code')
            if code != KdipCodeStatusTypes.SUCCESS:
                if 'access-token' in str(response_json.get('msg', '')).lower():
                    KdipServer.get_access_token_once()
                    return KdipServer.kdip_post(route, user_name, environment_type, data, headers, need_access_token)
                KdipServer._log('error', f'KdipServer kdip_post failed: {response_json}')
                return KdipCodeStatusTypes.FAILED
            return response_json.get('data', data)
        except requests.exceptions.RequestException as http_error:
            KdipServer._log('error', f'KdipServer kdip_post failed: {http_error}')
            return KdipCodeStatusTypes.FAILED

    @staticmethod
    def get_access_token_once():
        if not KdipServer._has_kdip_credential():
            KdipServer._log('warning', 'KDIP credential is empty, skip get_access_token_once')
            return KdipCodeStatusTypes.FAILED

        url = (f'https://open.kuaishou.com/oauth2/access_token?grant_type={KdipConfigArgs.GRANT_TYPE}'
               f'&app_id={KdipConfigArgs.APP_ID}&app_secret={KdipConfigArgs.APP_SECRETE}&scope={KdipConfigArgs.SCOPE}')
        try:
            res = requests.get(url, timeout=config.KDIP_REQUEST_TIMEOUT)
            res.raise_for_status()
            response_json = res.json()
            access_token = str(response_json.get('access_token', '')).strip()
            if not access_token:
                KdipServer._log('error', f'KdipServer get_access_token_once failed: {response_json}')
                return KdipCodeStatusTypes.FAILED
            KdipServer.access_token = access_token
            KdipServer.save_access_token()
            KdipServer._log('info', 'KdipServer get_access_token_once successfully')
            return KdipCodeStatusTypes.SUCCESS
        except requests.exceptions.RequestException as http_err:
            KdipServer._log('error', f'KdipServer get_access_token_once error: {http_err}')
            return KdipCodeStatusTypes.FAILED

    @staticmethod
    def get_zone_server_list(environment_type=EnvironmentTypes.ONLINE):
        return KdipServer.kdip_get(KdipGetRoute.SERVER_LIST, environment_type, True)

    @staticmethod
    def get_channel_list(environment_type=EnvironmentTypes.ONLINE):
        return KdipServer.kdip_get(KdipGetRoute.CHANNEL_LIST, environment_type, True)

    @staticmethod
    def get_platform_list(environment_type=EnvironmentTypes.ONLINE):
        return KdipServer.kdip_get(KdipGetRoute.PLATFORM_LIST, environment_type, True)

    @staticmethod
    def send_extend_cmd(user_name, environment_type: EnvironmentTypes, data: Union[str, dict], headers=None):
        return KdipServer.kdip_post(KdipPostRoute.EXTEND_CMD, user_name, environment_type, data, headers, True)
