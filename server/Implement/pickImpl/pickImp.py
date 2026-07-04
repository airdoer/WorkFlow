import os
import re
import sys
import json
import time
import logging
import requests
import subprocess
import shutil
from datetime import datetime
from flask import request, jsonify, send_file
from urllib.parse import urlparse, parse_qs
from bson import BSON
from bson import json_util
from Implement.pickImpl.blobImp import BlobImp
import Implement.pickImpl.script.mongoImportUtils as mongoImportUtils
import Implement.pickImpl.script.databaseUtils as databaseUtils

logger = logging.getLogger(__name__)

# MongoDB导入导出工具的路径 (指向 server/MongoImport)
MONGO_IMPORT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'pickImpl'))
if os.path.exists(MONGO_IMPORT_PATH):
    if MONGO_IMPORT_PATH not in sys.path:
        sys.path.insert(0, MONGO_IMPORT_PATH)
    logger.info(f"Added MongoImport path: {MONGO_IMPORT_PATH}")
else:
    logger.warning(f"MongoImport path not found: {MONGO_IMPORT_PATH}")

# MongoDB 工具脚本路径
RESTORE_SCRIPT = os.path.join(MONGO_IMPORT_PATH, 'restoreData.sh')
DUMP_SCRIPT = os.path.join(MONGO_IMPORT_PATH, 'dumpData.sh')
HISTORY_FILE = os.path.join(MONGO_IMPORT_PATH, 'data/history.json')
HISTORY_DIR = os.path.join(MONGO_IMPORT_PATH, 'history')
# 检查脚本是否存在
MONGO_TOOLS_AVAILABLE = os.path.exists(RESTORE_SCRIPT)
os.makedirs(HISTORY_DIR, exist_ok=True) 
if MONGO_TOOLS_AVAILABLE:
    logger.info(f"MongoDB tools available: copyAccount={RESTORE_SCRIPT}")
else:
    logger.warning(f"MongoDB tools not found in {MONGO_IMPORT_PATH}")

def get_local_server():
    conf_path = os.path.join(MONGO_IMPORT_PATH, 'config/local_conf.json')
    
    if not os.path.exists(conf_path):
        return {
            'code': 1,
            'errMsg': '配置文件不存在'
        }
    
    with open(conf_path, 'r', encoding='utf-8') as f:
        conf = json.load(f)
    
    server_list = []
    for env, env_conf in conf.items():
        alias = env  # 默认别名为服务器名称
        if isinstance(env_conf, list):
            for info in env_conf:
                if info.get("group_type") == "mongodb":
                    alias = info.get("alias", env)
                    break
        # 生成显示标签：别名 : 服务器名称
        label = f"{alias} : {env}"
        server_list.append({
            'label': label,
            'value': env,
            'alias': alias
        })
    
    return {
        'code': 0,
        'data': server_list
    }

def get_test_server():
    external_url = 'https://private-server.staging.kuaishou.com/api/open/serverList'
    
    # 调用外部接口获取配置
    logger.info(f"Fetching config from {external_url}")
    response = requests.get(external_url, timeout=10)
    response.raise_for_status()

    config_data = response.json()
    all_data = config_data.get('data')
    if not all_data:
        return {
            'code': 1,
            'errMsg': '请求云私服列表错误'
        }

    server_list = []
    for data in all_data:
        name = data.get('name', '')
        owner = data.get('owner', '')
        if name and owner:
            label = f"{owner} : {name}"
            server_list.append({
                'label': label,
                'value': name,
                'alias': owner
            })
    
    return {
        'code': 0,
        'data': server_list
    }

def get_logic_server():
    conf_path = os.path.join(MONGO_IMPORT_PATH, 'config/logic_conf.json')
    
    if not os.path.exists(conf_path):
        return {
            'code': 1,
            'errMsg': '配置文件不存在'
        }
    
    with open(conf_path, 'r', encoding='utf-8') as f:
        conf = json.load(f)
    
    server_list = []
    for env, env_conf in conf.items():
        for info in env_conf:
            if info["group_type"] == "mongodb":
                alias = info.get("alias", env)
                label = f"{alias} : {env}"
                server_list.append({'label': label, 'value': env})
    
    return {
        'code': 0,
        'data': server_list
    }

def save_history(entry):
    """保存操作历史到文件，并将dump文件复制到history文件夹"""
    try:
        history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        
        history.append(entry)
        
        # 只保留最近100条记录
        if len(history) > 100:
            history = history[-100:]
        
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
            
        logger.info(f"History entry saved successfully")
    except Exception as e:
        logger.error(f"Failed to save history: {e}")

def get_history():
    if not os.path.exists(HISTORY_FILE):
        return {
            'code': 0,
            'history': []
        }
    
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)
    
    # 反转列表，最新的在前面
    history.reverse()
    
    return {
        'code': 0,
        'history': history
    }

def get_dump_file(file_path):
    logger.info(f"Getting dump files from path: {file_path}")
    if not os.path.exists(file_path):
        return {
            'code': 1,
            'errMsg': f'文件目录不存在: {file_path}'
        }
    bson_files = [f for f in os.listdir(file_path) if f.lower().endswith('.bson')]

    content = {}
    for bson_file in bson_files:
        full_path = os.path.join(file_path, bson_file)
        try:
            with open(full_path, 'rb') as f:
                data_bson = f.read()
            doc = BSON(data_bson).decode()
            json_str = json_util.dumps(doc)
            json_doc = json.loads(json_str)

            content[bson_file] = json_doc
            return {
                'code': 0,
                'data': content
            }
        except Exception as e:
            return {
                'code': 1,
                'errMsg': f'读取文件 {bson_file} 失败: {str(e)}',
                'data': {}
            }


def local_to_local(source_logic_id, target_logic_id, dest_account, export_avatar_ids, short_uid, regen_avatar_id=False):
    # 本地到本地: 执行实际迁移
    start_time = datetime.now()
    
    try:
        avatar_id_str = export_avatar_ids

        logger.info(f"src_logic_id={source_logic_id}, "
                    f"dst_logic_id={target_logic_id}, dest_account={dest_account}, "
                    f"avatar_ids={avatar_id_str}, short_uid={short_uid}")
        
        CONF_PATH = "/app/Implement/pickImpl/config/local_conf.json"
        with open(CONF_PATH, "r", encoding="utf-8") as f:
            conf = json.load(f)

        db_info = {}
        for data in conf[source_logic_id]:
            if data['group_type'] == "mongodb":
                db_info['username'] = data['username']
                db_info['password'] = data['password']
                db_info['hosts'] = data['hosts']
                db_info['auth_source'] = data['auth_source']
                break
        
        logger.info(f'{db_info}')
        target_db = databaseUtils.mongoClientConnectLogic(db_info, source_logic_id)
        if target_db is None:
            logger.info("连接source数据库失败！")
            return {
                'code': 1,
                'errMsg': f'连接source数据库失败'
            }

        dump_conf = {
            "Account": [],
            "AvatarID": avatar_id_str,
            "ShortUID": short_uid,
            "Service": [],
            "Collection": {},
        }

        file_path = os.path.join(MONGO_IMPORT_PATH, 'data')
        save_file_dir = os.path.join(file_path, f'{source_logic_id}_{time.time()}')
        os.makedirs(save_file_dir, exist_ok=True)
        if not mongoImportUtils.dump_to_file(target_db, dump_conf, {}, save_file_dir):
            logger.error("dump file 失败")
            return {
                'code': 1,
                'errMsg': f'dump file 失败'
            }
            
        
        dest_account = dest_account if dest_account else 'test'
        if target_logic_id not in conf:
            logger.error("找不到目标Server，请检查参数")
            return {
                'code': 1,
                'errMsg': f'没有对应目标配置！'
            }
        
        if target_logic_id != source_logic_id:
            db_info = {}
            for data in conf[target_logic_id]:
                if data['group_type'] == "mongodb":
                    db_info['username'] = data['username']
                    db_info['password'] = data['password']
                    db_info['hosts'] = data['hosts']
                    db_info['auth_source'] = data['auth_source']
                    break
            target_db = databaseUtils.mongoClientConnectLogic(db_info, target_logic_id)
            if target_db is None:
                logger.error("连接数据库失败！")
                return {
                    'code': 1,
                    'errMsg': f'找不到目标数据库！'
                }

        if not mongoImportUtils.restore_from_file(target_db, save_file_dir, dest_account, regen_avatar_id=regen_avatar_id):
            logger.error("restore 失败")
            return {
                'code': 1,
                'errMsg': f'恢复数据失败！'
            }

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"Migration completed successfully in {duration:.2f}s")
        
        # 记录历史
        history_entry = {
            'timestamp': start_time.isoformat(),
            'operation': 'migrate',
            'sourceEnv': "local",
            'sourceLogicId': source_logic_id,
            'targetEnv': "local",
            'targetLogicId': target_logic_id,
            'exportAvatarIds': export_avatar_ids,
            'shortUid': short_uid,
            'destAccount': dest_account,
            'duration': duration,
            'status': 'success',
            'dumpDir': save_file_dir
        }

        save_history(history_entry)

        return {
            'code': 0,
            'data': {
                'message': '数据迁移成功',
                'duration': f'{duration:.2f}',
                'destAccount': dest_account,
            }
        }
        
    except subprocess.TimeoutExpired:
        return {
            'code': 1,
            'errMsg': '数据迁移超时(超过5分钟)'
        }
    except Exception as inner_e:
        logger.error(f"Migration execution error: {inner_e}", exc_info=True)
        return {
            'code': 1,
            'errMsg': f'迁移执行失败: {str(inner_e)}'
        }
    
def _parse_loose_json_dict(raw_data):
    if isinstance(raw_data, dict):
        return raw_data

    if raw_data is None:
        raise ValueError('配置内容为空')

    text = str(raw_data)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        return json.loads(text.replace("'", '"'))
    except json.JSONDecodeError:
        pass

    import ast
    return ast.literal_eval(text)


def _fetch_test_config_data(logic_id, config_file='docker_config_new.json'):
    external_url = 'https://private-server.staging.kuaishou.com/api/open/readFile'
    params = {
        'server': str(logic_id),
        'path': f'/Server/config/{config_file}',
    }

    logger.info(f"Fetching config from {external_url}, server={logic_id}, file={config_file}")
    response = requests.get(external_url, params=params, timeout=10)
    response.raise_for_status()

    config_data = response.json()
    if config_data.get('errCode', 0) != 0:
        raise ValueError(f"请求云私服配置失败: {config_data.get('errMsg', '未知错误')}")

    raw_data = config_data.get('data')
    if raw_data is None or raw_data == '':
        raise ValueError(f"请求云私服配置失败: 返回data为空, file={config_file}")

    if isinstance(raw_data, dict):
        if 'common' in raw_data or 'dbmgr' in raw_data:
            return raw_data
        if config_file in raw_data:
            raw_data = raw_data.get(config_file)
        elif len(raw_data) == 1:
            raw_data = next(iter(raw_data.values()))

    data = _parse_loose_json_dict(raw_data)
    if not isinstance(data, dict):
        raise ValueError(f'云私服配置格式错误: {config_file}')

    return data


def _list_test_config_files(logic_id):
    external_url = 'https://private-server.staging.kuaishou.com/api/open/readFile'
    params = {
        'server': str(logic_id),
        'path': '/Server/config',
    }

    logger.info(f"Listing config files from {external_url}, server={logic_id}")
    response = requests.get(external_url, params=params, timeout=20)
    response.raise_for_status()

    config_data = response.json()
    if config_data.get('errCode', 0) != 0:
        raise ValueError(f"请求云私服配置列表失败: {config_data.get('errMsg', '未知错误')}")

    raw_data = config_data.get('data')
    if not isinstance(raw_data, dict):
        raise ValueError('云私服配置目录返回格式错误，预期为字典')

    selected_files = []
    if 'docker_config_new.json' in raw_data:
        selected_files.append('docker_config_new.json')

    single_files = [
        filename for filename in raw_data.keys()
        if re.match(r'^docker_config_single_.+_new\.json$', str(filename))
    ]
    selected_files.extend(sorted(single_files))

    # 去重并保持顺序
    seen = set()
    deduped_files = []
    for filename in selected_files:
        if filename in seen:
            continue
        seen.add(filename)
        deduped_files.append(filename)

    return deduped_files


def _test_config_file_exists(logic_id, config_file='docker_config_new.json'):
    external_url = 'https://private-server.staging.kuaishou.com/api/open/readFile'
    params = {
        'server': str(logic_id),
        'path': f'/Server/config/{config_file}',
    }

    try:
        logger.info(f"Checking config file exists from {external_url}, server={logic_id}, file={config_file}")
        response = requests.get(external_url, params=params, timeout=10)
        response.raise_for_status()
        config_data = response.json()
        if config_data.get('errCode', 0) != 0:
            return False
        raw_data = config_data.get('data')
        return raw_data is not None and raw_data != ''
    except Exception:
        return False


def get_test_config_files(logic_id):
    try:
        # 需求：优先探测 docker_config_new.json，若存在则只返回该文件
        if _test_config_file_exists(logic_id, 'docker_config_new.json'):
            config_files = ['docker_config_new.json']
        else:
            # 若默认文件不存在，再返回 docker_config_single_xx_new.json 列表
            listed_files = _list_test_config_files(logic_id)
            config_files = [
                filename for filename in listed_files
                if re.match(r'^docker_config_single_.+_new\.json$', str(filename))
            ]

        return {
            'code': 0,
            'data': [
                {
                    'label': filename,
                    'value': filename
                }
                for filename in config_files
            ],
            'defaultSelect': config_files[0] if config_files else ''
        }
    except Exception as e:
        logger.error(f"get_test_config_files error: {e}", exc_info=True)
        return {
            'code': 1,
            'errMsg': str(e)
        }


def _get_test_db_info(logic_id, config_file='docker_config_new.json'):
    data = _fetch_test_config_data(logic_id, config_file)

    common = data.get('common') or {}
    dbmgr = data.get('dbmgr') or {}
    logic_server_list = common.get('logic_server_list') or []
    if not logic_server_list:
        raise ValueError(f'云私服配置缺少 logic_server_list: {config_file}')

    logic_server_id = str(logic_server_list[0])
    server_name = f'{logic_id}_{logic_server_id}'
    mongo_cluster = dbmgr.get('mongo_cluster') or {}
    db_info = mongo_cluster.get(server_name)

    if not db_info:
        # 兜底：跨服命名可能不是 {logic_id}_{server_id}
        for key, value in mongo_cluster.items():
            key_str = str(key)
            if key_str.endswith(f'_{logic_server_id}') and not key_str.endswith('_main'):
                server_name = key_str
                db_info = value
                break

    if not db_info:
        raise ValueError(f'云私服配置中不存在目标mongo配置: {server_name}, file={config_file}')

    return db_info, server_name


def _connect_test_logic_db(logic_id, config_file='docker_config_new.json'):
    db_info, server_name = _get_test_db_info(logic_id, config_file)
    logger.info(f'Connecting test db: server_name={server_name}, file={config_file}')
    target_db = databaseUtils.mongoClientConnectLogic(db_info, server_name)
    if target_db is None:
        raise ValueError(f'连接云私服数据库失败: {server_name}, file={config_file}')
    return target_db, server_name


def local_to_test(source_logic_id, target_logic_id, dest_account, export_avatar_ids, short_uid, regen_avatar_id=False, target_config_file='docker_config_new.json'):

    start_time = datetime.now()
    try:
        CONF_PATH = "/app/Implement/pickImpl/config/local_conf.json"
        with open(CONF_PATH, "r", encoding="utf-8") as f:
            conf = json.load(f)

        if source_logic_id not in conf:
            return {
                'code': 1,
                'errMsg': '没有对应源环境配置！'
            }

        source_db_info = {}
        for data in conf[source_logic_id]:
            if data['group_type'] == "mongodb":
                source_db_info['username'] = data['username']
                source_db_info['password'] = data['password']
                source_db_info['hosts'] = data['hosts']
                source_db_info['auth_source'] = data['auth_source']
                break

        source_db = databaseUtils.mongoClientConnectLogic(source_db_info, source_logic_id)
        if source_db is None:
            return {
                'code': 1,
                'errMsg': '连接source数据库失败'
            }

        dump_conf = {
            "Account": [],
            "AvatarID": export_avatar_ids,
            "ShortUID": short_uid,
            "Service": [],
            "Collection": {},
        }

        save_file_dir = os.path.join(MONGO_IMPORT_PATH, 'data', f'{source_logic_id}_{time.time()}')
        os.makedirs(save_file_dir, exist_ok=True)
        if not mongoImportUtils.dump_to_file(source_db, dump_conf, {}, save_file_dir):
            return {
                'code': 1,
                'errMsg': 'dump file 失败'
            }

        dest_account = dest_account if dest_account else 'test'
        target_db, _ = _connect_test_logic_db(target_logic_id, target_config_file)

        if not mongoImportUtils.restore_from_file(target_db, save_file_dir, dest_account, regen_avatar_id=regen_avatar_id):
            return {
                'code': 1,
                'errMsg': '恢复数据失败！'
            }

        duration = (datetime.now() - start_time).total_seconds()
        history_entry = {
            'timestamp': start_time.isoformat(),
            'operation': 'migrate',
            'sourceEnv': 'local',
            'sourceLogicId': source_logic_id,
            'targetEnv': 'test',
            'targetLogicId': target_logic_id,
            'exportAvatarIds': export_avatar_ids,
            'shortUid': short_uid,
            'destAccount': dest_account,
            'duration': duration,
            'status': 'success',
            'dumpDir': save_file_dir
        }
        save_history(history_entry)

        return {
            'code': 0,
            'data': {
                'message': '数据迁移成功',
                'duration': f'{duration:.2f}',
                'destAccount': dest_account,
            }
        }
    except subprocess.TimeoutExpired:
        return {
            'code': 1,
            'errMsg': '数据迁移超时(超过5分钟)'
        }
    except Exception as inner_e:
        logger.error(f"Migration execution error: {inner_e}", exc_info=True)
        return {
            'code': 1,
            'errMsg': f'迁移执行失败: {str(inner_e)}'
        }

def test_to_local(source_logic_id, target_logic_id, dest_account, export_avatar_ids, short_uid, regen_avatar_id=False, source_config_file='docker_config_new.json'):
    start_time = datetime.now()
    try:
        source_db, _ = _connect_test_logic_db(source_logic_id, source_config_file)

        dump_conf = {
            "Account": [],
            "AvatarID": export_avatar_ids,
            "ShortUID": short_uid,
            "Service": [],
            "Collection": {},
        }

        save_file_dir = os.path.join(MONGO_IMPORT_PATH, 'data', f'{source_logic_id}_{time.time()}')
        os.makedirs(save_file_dir, exist_ok=True)
        if not mongoImportUtils.dump_to_file(source_db, dump_conf, {}, save_file_dir):
            return {
                'code': 1,
                'errMsg': 'dump file 失败'
            }

        CONF_PATH = "/app/Implement/pickImpl/config/local_conf.json"
        with open(CONF_PATH, "r", encoding="utf-8") as f:
            conf = json.load(f)

        if target_logic_id not in conf:
            return {
                'code': 1,
                'errMsg': '没有对应目标配置！'
            }

        target_db_info = {}
        for data in conf[target_logic_id]:
            if data['group_type'] == "mongodb":
                target_db_info['username'] = data['username']
                target_db_info['password'] = data['password']
                target_db_info['hosts'] = data['hosts']
                target_db_info['auth_source'] = data['auth_source']
                break

        target_db = databaseUtils.mongoClientConnectLogic(target_db_info, target_logic_id)
        if target_db is None:
            return {
                'code': 1,
                'errMsg': '找不到目标库！'
            }

        dest_account = dest_account if dest_account else 'test'
        if not mongoImportUtils.restore_from_file(target_db, save_file_dir, dest_account, regen_avatar_id=regen_avatar_id):
            return {
                'code': 1,
                'errMsg': '恢复数据失败！'
            }

        duration = (datetime.now() - start_time).total_seconds()
        history_entry = {
            'timestamp': start_time.isoformat(),
            'operation': 'migrate',
            'sourceEnv': 'test',
            'sourceLogicId': source_logic_id,
            'targetEnv': 'local',
            'targetLogicId': target_logic_id,
            'exportAvatarIds': export_avatar_ids,
            'shortUid': short_uid,
            'destAccount': dest_account,
            'duration': duration,
            'status': 'success',
            'dumpDir': save_file_dir
        }
        save_history(history_entry)

        return {
            'code': 0,
            'data': {
                'message': '数据迁移成功',
                'duration': f'{duration:.2f}',
                'destAccount': dest_account,
            }
        }
    except subprocess.TimeoutExpired:
        return {
            'code': 1,
            'errMsg': '数据迁移超时(超过5分钟)'
        }
    except Exception as inner_e:
        logger.error(f"Migration execution error: {inner_e}", exc_info=True)
        return {
            'code': 1,
            'errMsg': f'迁移执行失败: {str(inner_e)}'
        }

def test_to_test(source_logic_id, target_logic_id, dest_account, export_avatar_ids, short_uid, regen_avatar_id=False, source_config_file='docker_config_new.json', target_config_file='docker_config_new.json'):
    start_time = datetime.now()
    try:
        source_db, _ = _connect_test_logic_db(source_logic_id, source_config_file)

        dump_conf = {
            "Account": [],
            "AvatarID": export_avatar_ids,
            "ShortUID": short_uid,
            "Service": [],
            "Collection": {},
        }

        save_file_dir = os.path.join(MONGO_IMPORT_PATH, 'data', f'{source_logic_id}_{time.time()}')
        os.makedirs(save_file_dir, exist_ok=True)
        if not mongoImportUtils.dump_to_file(source_db, dump_conf, {}, save_file_dir):
            return {
                'code': 1,
                'errMsg': 'dump file 失败'
            }

        target_db, _ = _connect_test_logic_db(target_logic_id, target_config_file)
        dest_account = dest_account if dest_account else 'test'

        if not mongoImportUtils.restore_from_file(target_db, save_file_dir, dest_account, regen_avatar_id=regen_avatar_id):
            return {
                'code': 1,
                'errMsg': '恢复数据失败！'
            }

        duration = (datetime.now() - start_time).total_seconds()
        history_entry = {
            'timestamp': start_time.isoformat(),
            'operation': 'migrate',
            'sourceEnv': 'test',
            'sourceLogicId': source_logic_id,
            'targetEnv': 'test',
            'targetLogicId': target_logic_id,
            'exportAvatarIds': export_avatar_ids,
            'shortUid': short_uid,
            'destAccount': dest_account,
            'duration': duration,
            'status': 'success',
            'dumpDir': save_file_dir
        }
        save_history(history_entry)

        return {
            'code': 0,
            'data': {
                'message': '数据迁移成功',
                'duration': f'{duration:.2f}',
                'destAccount': dest_account,
            }
        }
    except subprocess.TimeoutExpired:
        return {
            'code': 1,
            'errMsg': '数据迁移超时(超过5分钟)'
        }
    except Exception as inner_e:
        logger.error(f"Migration execution error: {inner_e}", exc_info=True)
        return {
            'code': 1,
            'errMsg': f'迁移执行失败: {str(inner_e)}'
        }

def weekly_to_local(source_logic_id, target_logic_id, dest_account, export_avatar_ids, short_uid, regen_avatar_id=False):
    # 从外网环境迁移到内网环境中
    if not MONGO_TOOLS_AVAILABLE:
        return {
            'code': 1,
            'errMsg': 'MongoDB工具不可用,请检查服务器配置'
        }
    
    start_time = datetime.now()
    
    try:
        # 外部接口地址
        external_url = 'https://ksgame-c7-pick.test.gifshow.com/dump_db_data'
        
        # 准备请求头
        headers = {
            'X-User': 'c7',
            'X-Token': 'r949dXPwWRN6CAP98MsCMZjfi8jqYmTK',
            'Content-Type': 'application/json'
        }
        
        # 处理角色ID
        target_avatar_id = ""
        for id in export_avatar_ids:
            target_avatar_id += f'{id},'
        target_avatar_id = target_avatar_id[:-1]

        target_short_uid = ""
        for uid in short_uid:
            target_short_uid += f'{uid},'
        target_short_uid = target_short_uid[:-1]
        
        if not target_avatar_id and not target_short_uid:
            return {
                'code': 1,
                'errMsg': '必须指定目标角色ID或角色UID'
            }
        
        # 构建请求体
        payload = {
            'targetserver': str(source_logic_id),
            'targetavatarid': target_avatar_id,
            'targetshortuid': target_short_uid
        }
        
        logger.info(f"Calling external API: {external_url}")
        logger.info(f"Payload: {json.dumps(payload)}")
        
        # 调用外部接口
        response = requests.post(
            external_url,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        dump_response = response.json()
        logger.info(f"External API response: {json.dumps(dump_response)}")
        
        if not dump_response.get('success'):
            error_msg = dump_response.get('error', '数据导出失败')
            return {
                'code': 1,
                'errMsg': f'Weekly 数据导出失败: {error_msg}'
            }
        
        file_name = dump_response.get('file_name', '')
        file_path = dump_response.get('file_path', '')
        blob_prefix = dump_response.get('blob_prefix', '')
        
        if not file_name or not file_path:
            return {
                'code': 1,
                'errMsg': '导出文件信息不完整'
            }
        
        logger.info(f"Export successful: file_name={file_name}, file_path={file_path}")

        file_name = file_name.split('/')[-1]
        save_file_dir = os.path.join(MONGO_IMPORT_PATH, 'data', file_name)
        success, msg = download_from_blob(blob_prefix, save_file_dir)

        if not success:
            return {
                'code': 1,
                'errMsg': f'文件下载失败: {msg}'
            }

        # 使用子进程调用 restoreData.sh脚本 导入数据
        CONF_PATH = "/app/Implement/pickImpl/config/local_conf.json"
        with open(CONF_PATH, "r", encoding="utf-8") as f:
            conf = json.load(f)

        if target_logic_id not in conf:
            logger.error("找不到对应Server，请检查参数")
            return {
                'code': 1,
                'errMsg': f'没有对应目标配置！'
            }
        
        db_info = {}
        for data in conf[target_logic_id]:
            if data['group_type'] == "mongodb":
                db_info['username'] = data['username']
                db_info['password'] = data['password']
                db_info['hosts'] = data['hosts']
                db_info['auth_source'] = data['auth_source']
                break
        target_db = databaseUtils.mongoClientConnectLogic(db_info, target_logic_id)
        if target_db is None:
            logger.error("连接数据库失败！")
            return {
                'code': 1,
                'errMsg': f'找不到目标库！'
            }

        if not mongoImportUtils.restore_from_file(target_db, save_file_dir, dest_account, regen_avatar_id=regen_avatar_id):
            logger.error("restore 失败")
            return {
                'code': 1,
                'errMsg': f'恢复数据失败！'
            }
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"Migration completed successfully in {duration:.2f}s")

        # 记录历史
        history_entry = {
            'timestamp': start_time.isoformat(),
            'operation': 'migrate',
            'sourceEnv': "weekly",
            'sourceLogicId': source_logic_id,
            'targetEnv': "local",
            'targetLogicId': target_logic_id,
            'exportAvatarIds': export_avatar_ids,
            'shortUid': short_uid,
            'destAccount': dest_account,
            'duration': duration,
            'status': 'success',
            'dumpDir': save_file_dir
        }

        save_history(history_entry)

        return {
            'code': 0,
            'data': {
                'message': '数据导出成功'
            }
        }
        
    except subprocess.TimeoutExpired:
        return {
            'code': 1,
            'errMsg': '数据迁移超时(超过5分钟)'
        }
    except Exception as inner_e:
        logger.error(f"Migration execution error: {inner_e}", exc_info=True)
        return {
            'code': 1,
            'errMsg': f'迁移执行失败: {str(inner_e)}'
        }
    
def weekly_to_test(source_logic_id, target_logic_id, dest_account, export_avatar_ids, short_uid, regen_avatar_id=False, target_config_file='docker_config_new.json'):
    # 从外网环境迁移到云私服环境中
    if not MONGO_TOOLS_AVAILABLE:
        return {
            'code': 1,
            'errMsg': 'MongoDB工具不可用,请检查服务器配置'
        }
    
    start_time = datetime.now()
    
    try:
        # 外部接口地址
        external_url = 'https://ksgame-c7-pick.test.gifshow.com/dump_db_data'
        
        # 准备请求头
        headers = {
            'X-User': 'c7',
            'X-Token': 'r949dXPwWRN6CAP98MsCMZjfi8jqYmTK',
            'Content-Type': 'application/json'
        }
        
        # 处理角色ID
        target_avatar_id = ""
        for id in export_avatar_ids:
            target_avatar_id += f'{id},'
        target_avatar_id = target_avatar_id[:-1]

        target_short_uid = ""
        for uid in short_uid:
            target_short_uid += f'{uid},'
        target_short_uid = target_short_uid[:-1]
        
        if not target_avatar_id and not target_short_uid:
            return {
                'code': 1,
                'errMsg': '必须指定目标角色ID或角色UID'
            }
        
        # 构建请求体
        payload = {
            'targetserver': str(source_logic_id),
            'targetavatarid': target_avatar_id,
            'targetshortuid': target_short_uid
        }
        
        logger.info(f"Calling external API: {external_url}")
        logger.info(f"Payload: {json.dumps(payload)}")
        
        # 调用外部接口
        response = requests.post(
            external_url,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        dump_response = response.json()
        logger.info(f"External API response: {json.dumps(dump_response)}")
        
        if not dump_response.get('success'):
            error_msg = dump_response.get('error', '数据导出失败')
            return {
                'code': 1,
                'errMsg': f'Weekly 数据导出失败: {error_msg}'
            }
        
        file_name = dump_response.get('file_name', '')
        file_path = dump_response.get('file_path', '')
        blob_prefix = dump_response.get('blob_prefix', '')
        
        if not file_name or not file_path:
            return {
                'code': 1,
                'errMsg': '导出文件信息不完整'
            }
        
        logger.info(f"Export successful: file_name={file_name}, file_path={file_path}")

        file_name = file_name.split('/')[-1]
        save_file_dir = os.path.join(MONGO_IMPORT_PATH, 'data', file_name)
        success, msg = download_from_blob(blob_prefix, save_file_dir)

        if not success:
            return {
                'code': 1,
                'errMsg': f'文件下载失败: {msg}'
            }
        target_db, _ = _connect_test_logic_db(target_logic_id, target_config_file)

        if not mongoImportUtils.restore_from_file(target_db, save_file_dir, dest_account, regen_avatar_id=regen_avatar_id):
            logger.error("restore 失败")
            return {
                'code': 1,
                'errMsg': f'恢复数据失败！'
            }
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"Migration completed successfully in {duration:.2f}s")

        # 记录历史
        history_entry = {
            'timestamp': start_time.isoformat(),
            'operation': 'migrate',
            'sourceEnv': "weekly",
            'sourceLogicId': source_logic_id,
            'targetEnv': "test",
            'targetLogicId': target_logic_id,
            'exportAvatarIds': export_avatar_ids,
            'destAccount': dest_account,
            'duration': duration,
            'status': 'success',
            'dumpDir': save_file_dir
        }

        save_history(history_entry)

        return {
            'code': 0,
            'data': {
                'message': '数据导出成功'
            }
        }
        
    except subprocess.TimeoutExpired:
        return {
            'code': 1,
            'errMsg': '数据迁移超时(超过5分钟)'
        }
    except Exception as inner_e:
        logger.error(f"Migration execution error: {inner_e}", exc_info=True)
        return {
            'code': 1,
            'errMsg': f'迁移执行失败: {str(inner_e)}'
        }
    
def download_from_blob(blob_prefix, local_save_dir):
    # 从 blob 存储下载文件

    blob_client = None
    try:
        blob_client = BlobImp()
        
        # 确保保存目录存在
        os.makedirs(local_save_dir, exist_ok=True)
        
        logger.info(f"Starting blob download from prefix: {blob_prefix} to {local_save_dir}")

        # 列出所有对象
        res, data = blob_client.list_objects(blob_prefix)
        
        if not res:
            return False, f"列出对象失败: {data}"

        logger.info(f"Found {len(data)} objects to download")
        
        downloaded_files = []
        failed_files = []
        
        # 逐个下载文件
        for item in data:
            try:
                file_name = item["key"].split('/')[-1]
                file_path = os.path.join(local_save_dir, file_name)
                
                success, msg = blob_client.download(item["key"], file_path)
                
                if success:
                    logger.info(f'Successfully downloaded: {item["key"]} to {file_path}')
                    downloaded_files.append(file_path)
                else:
                    logger.error(f'Failed to download: {item["key"]} to {file_path}, error: {msg}')
                    failed_files.append({'key': item["key"], 'error': msg})
            except Exception as file_e:
                logger.error(f'Error downloading file {item["key"]}: {file_e}', exc_info=True)
                failed_files.append({'key': item["key"], 'error': str(file_e)})
        
        if failed_files:
            error_summary = f"下载完成，但有 {len(failed_files)} 个文件失败: {json.dumps(failed_files)}"
            logger.warning(error_summary)
            return False, error_summary
        
        success_msg = f"成功下载 {len(downloaded_files)} 个文件"
        logger.info(success_msg)
        return True, success_msg
        
    except Exception as e:
        logger.error(f"Download from blob error: {e}", exc_info=True)
        return False, f"下载出错: {str(e)}"
    finally:
        # 确保清理资源
        if blob_client:
            try:
                blob_client.close()
            except Exception as cleanup_e:
                logger.warning(f"Error closing blob client: {cleanup_e}")

        if not data or len(data) == 0:
            return False, "数据库中未查找到对应ID的角色"
        if res:
            logger.info(f"list File successfully")
            return True, "读取文件列表成功"
        else:
            logger.error(f"list File error")
            return False, f"读取文件列表失败"
            

def request_config():
    # 外部接口地址
        external_url = 'https://ksgame-c7-pick.test.gifshow.com/get_c7_db_info'
        
        # 准备请求头
        headers = {
            'X-User': 'c7',
            'X-Token': 'r949dXPwWRN6CAP98MsCMZjfi8jqYmTK',
            'Content-Type': 'application/json'
        }
        
        # 调用外部接口获取配置
        logger.info(f"Fetching config from {external_url}")
        response = requests.get(external_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        config_data = response.json()
        logger.info(f"Successfully fetched config from external service")
        
        # 配置文件保存路径
        conf_path = os.path.join(MONGO_IMPORT_PATH, 'config/logic_conf.json')
        
        # 保存配置到文件
        with open(conf_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Config saved to {conf_path}")
        
        return {
            'code': 0,
            'data': config_data,
            'message': f'Config update'
        }

def upload_local_config(name, hosts, alias=''):
    """上传单个本地服务器配置到 local_conf.json"""
    
    try:
        if not name or not isinstance(name, str):
            return {
                'code': 1,
                'errMsg': '服务器名称不能为空且必须是字符串'
            }
        
        # 如果hosts为空或者列表为空，使用默认值
        if not hosts or not isinstance(hosts, list) or len(hosts) == 0:
            hosts = ['172.20.5.92:27017']
        
        # 配置文件保存路径
        conf_path = os.path.join(MONGO_IMPORT_PATH, 'config/local_conf.json')
        
        # 确保目录存在
        os.makedirs(os.path.dirname(conf_path), exist_ok=True)
        
        # 读取现有配置（如果存在）
        existing_config = {}
        if os.path.exists(conf_path):
            try:
                with open(conf_path, 'r', encoding='utf-8') as f:
                    existing_config = json.load(f)
                logger.info(f"Loaded existing config from {conf_path}")
            except Exception as e:
                logger.warning(f"Failed to load existing config: {e}")
        
        # 如果别名为空，使用服务器名称作为别名
        display_alias = alias.strip() if alias else name
        
        # 添加或更新指定的服务器配置
        existing_config[name] = [{
            "group_name": "mongodb_groups4",
            "hosts": hosts,
            "alias": display_alias,
            "username": "root",
            "password": "Zu4tK7vZFmfzWcE4YU",
            "auth_source": "admin",
            "group_type": "mongodb",
            "group_usage": "gs"
        }]
        
        # 保存合并后的配置
        with open(conf_path, 'w', encoding='utf-8') as f:
            json.dump(existing_config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Server config '{name}' (alias: '{display_alias}') saved to {conf_path}")
        
        return {
            'code': 0,
            'data': existing_config,
            'message': f'服务器配置 "{display_alias}: {name}" 已保存，共 {len(existing_config)} 个服务器配置'
        }
    
    except IOError as io_e:
        logger.error(f"Failed to write config file: {io_e}", exc_info=True)
        return {
            'code': 1,
            'errMsg': f'无法保存配置文件: {str(io_e)}'
        }
    except Exception as e:
        logger.error(f"upload_local_config error: {e}", exc_info=True)
        return {
            'code': 1,
            'errMsg': f'上传配置失败: {str(e)}'
        }

def delete_local_config(name):
    """从 local_conf.json 中删除指定的本地服务器配置"""
    
    try:
        if not name or not isinstance(name, str):
            return {
                'code': 1,
                'errMsg': '服务器名称不能为空且必须是字符串'
            }
        
        # 配置文件路径
        conf_path = os.path.join(MONGO_IMPORT_PATH, 'config/local_conf.json')
        
        # 检查配置文件是否存在
        if not os.path.exists(conf_path):
            return {
                'code': 1,
                'errMsg': '配置文件不存在'
            }
        
        # 读取现有配置
        try:
            with open(conf_path, 'r', encoding='utf-8') as f:
                existing_config = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
            return {
                'code': 1,
                'errMsg': f'读取配置文件失败: {str(e)}'
            }
        
        # 检查要删除的配置是否存在
        if name not in existing_config:
            return {
                'code': 1,
                'errMsg': f'服务器配置 "{name}" 不存在'
            }
        
        # 删除指定配置
        del existing_config[name]
        
        # 保存更新后的配置
        with open(conf_path, 'w', encoding='utf-8') as f:
            json.dump(existing_config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Server config '{name}' deleted from {conf_path}")
        
        return {
            'code': 0,
            'data': existing_config,
            'message': f'服务器配置 "{name}" 已删除，剩余 {len(existing_config)} 个服务器配置'
        }
    
    except IOError as io_e:
        logger.error(f"Failed to write config file: {io_e}", exc_info=True)
        return {
            'code': 1,
            'errMsg': f'无法保存配置文件: {str(io_e)}'
        }
    except Exception as e:
        logger.error(f"delete_local_config error: {e}", exc_info=True)
        return {
            'code': 1,
            'errMsg': f'删除配置失败: {str(e)}'
        }
