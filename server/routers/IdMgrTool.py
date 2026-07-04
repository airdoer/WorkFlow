# 和游戏服务器 战斗相关的route放这个里 这里只放对内的接口 对外的放battleExternal里

# builtin
import os
import shutil
from datetime import datetime

# 3rd ext
from flask import render_template, request, jsonify, Response
from sqlalchemy import and_

# int
from appImp import app
from dbImp.mongoImp import get_excel_id_mongo, get_excel_id_history_mongo
import logging
from utility import p4Utils
import config

logger = logging.getLogger(__name__)
# region init

# endregion

def _write_id_history(action: str, excel_name: str, sheet_name: str, id_val: str, operator: str, success: bool, err_msg: str = "", detail: dict = None):
    try:
        record = {
            "action": action,
            "excelName": excel_name,
            "sheetName": sheet_name,
            "id": id_val,
            "operator": operator or "",
            "success": bool(success),
            "errMsg": err_msg or "",
            "timestamp": datetime.now(),
            "detail": detail or {},
            "clientIp": request.remote_addr or ""
        }
        get_excel_id_history_mongo().add_history(record)
    except Exception as e:
        app.logger.error(f"write id history failed: {e}")


@app.route('/getIdMgrInfo', methods=['POST'])
def getIdMgrInfo():
    """获取ID管理器信息"""
    app.logger.info("czx getIdMgrInfo")
    
    return jsonify({
        'code': 0,
        'errMsg': ''
    })


@app.route('/importIdTestData', methods=['POST'])
def importIdTestData():
    """导入测试数据接口"""
    app.logger.info("czx importIdTestData")
    deleteAllIds()
    count = importTestData()
    return jsonify({
        'code': 0,
        'msg': f'Successfully imported {count} records',
        'count': count
    })

@app.route('/checkIdOccupy', methods=['POST'])
def checkIdOccupy():
    data = request.json or {}
    excel_name = data.get('excelName')
    sheet_name = data.get('sheetName')
    id_val = data.get('id')
    owner = data.get('owner')
    try:
        app.logger.info(f"czx checkIdOccupy: {excel_name=}, {sheet_name=}, {id_val=}, {owner=}")
        if not all([excel_name, sheet_name, id_val, owner]):
            app.logger.info(f"czx checkIdOccupy failed: {excel_name=}, {sheet_name=}, {id_val=}, {owner=}, missing required fields")
            return jsonify({'code': 1, 'errMsg': 'Missing required fields'})

        mongo_imp = get_excel_id_mongo()
        info = mongo_imp.collection.find_one(
            {"excelName": excel_name, "sheetName": sheet_name, "id": id_val},
            {"_id": 0, "owner": 1, "occupy": 1}
        )
        if not info:
            app.logger.info(f"czx checkIdOccupy failed: {excel_name=}, {sheet_name=}, {id_val=}, {owner=}, not found")
            return jsonify({'code': 1, 'errMsg': 'ID not found'})

        occupied_owner = info.get('owner') or ''
        if occupied_owner != owner and (occupied_owner != 'system' and owner != 'system'):
            app.logger.info(f"czx checkIdOccupy failed: {excel_name=}, {sheet_name=}, {id_val=}, {owner=}, occupied by {occupied_owner}")
            return jsonify({'code': 1, 'errMsg': f"ID is occupied by '{occupied_owner}'"})
        
        app.logger.info(f"czx checkIdOccupy success: {excel_name=}, {sheet_name=}, {id_val=}, {owner=}")
        return jsonify({'code': 0, 'msg': 'OK'})
    except Exception as e:
        app.logger.error(f"czx checkIdOccupy failed: {e} {excel_name=}, {sheet_name=}, {id_val=}, {owner=}")
        return jsonify({'code': 1, 'errMsg': str(e)})


@app.route('/checkIdDelete', methods=['POST'])
def checkIdDelete():
    try:
        data = request.json or {}
        excel_name = data.get('excelName')
        sheet_name = data.get('sheetName')
        id_val = data.get('id')
        app.logger.info(f"czx checkIdDelete: {excel_name=}, {sheet_name=}, {id_val=}")

        if not all([excel_name, sheet_name, id_val]):
            return jsonify({'code': 1, 'errMsg': 'Missing required fields'})

        mongo_imp = get_excel_id_mongo()
        info = mongo_imp.collection.find_one(
            {"excelName": excel_name, "sheetName": sheet_name, "id": id_val},
            {"_id": 0, "id": 1}
        )
        if info:
            return jsonify({'code': 1, 'errMsg': 'ID still exists'})

        return jsonify({'code': 0, 'msg': 'ID is deleted'})
    except Exception as e:
        app.logger.error(f"checkIdDelete failed: {e}")
        return jsonify({'code': 1, 'errMsg': str(e)})

@app.route('/listIdHistory', methods=['POST'])
def listIdHistory():
    try:
        data = request.json or {}
        query = data.get('query', {}) or {}
        limit = int(data.get('limit', 100))
        skip = int(data.get('skip', 0))

        mongo_imp = get_excel_id_history_mongo()
        items = mongo_imp.list_history(query, limit=limit, skip=skip)
        total = mongo_imp.count_history(query)

        return jsonify({
            'code': 0,
            'data': {
                'items': items,
                'total': total
            }
        })
    except Exception as e:
        app.logger.error(f"Failed to list id history: {e}")
        return jsonify({'code': 1, 'errMsg': str(e)})


@app.route('/addId', methods=['POST'])
def addId():
    """新增或修改 ID"""
    try:
        data = request.json
        app.logger.info(f"addId: {data}")
        excel_name = data.get('excelName')
        sheet_name = data.get('sheetName')
        branch = data.get('branch')
        owner = data.get('owner')
        id_val = data.get('id')
        
        if not all([excel_name, sheet_name, id_val]):
            return jsonify({'code': 1, 'errMsg': 'Missing required fields'})
            
        # 根据 ID 格式推断 level 和 parentId，并生成纯净的 path
        parts = id_val.split('-')
        if len(parts) == 1:
            level = "MainKey"
            parent_id = None
            path = [parts[0]]
        elif len(parts) == 2:
            level = "MainSub"
            parent_id = parts[0]
            path = [parts[0], parts[1]]
        elif len(parts) >= 3:
            level = "MainSubMinor"
            parent_id = f"{parts[0]}-{parts[1]}"
            path = [parts[0], parts[1], parts[2]]
        
        mongo_imp = get_excel_id_mongo()
        existed = mongo_imp.collection.find_one(
            {"excelName": excel_name, "sheetName": sheet_name, "id": id_val},
            {"_id": 0, "id": 1, "owner": 1, "updatedAt": 1, "allow_until": 1}
        )

        if branch is not None and branch != 'Mainline' and not existed:
            _write_id_history(
                "add_fail",
                data.get('excelName') or "",
                data.get('sheetName') or "",
                data.get('id') or "",
                data.get('owner') or "",
                False,
                "permission denied, non-mainline add requires mainline id exists",
                {"request": data}
            )
            return jsonify({'code': 1, 'errMsg': '新增id必须先在主干新增后才能在Weekly上提交'})

        if existed and (existed.get('owner') != owner):
            if existed.get('owner') == 'system':
                # 如果是系统占用，允许通过，并且不更改原记录
                app.logger.info(f"addId allowed system without overwrite: {excel_name=}, {sheet_name=}, {id_val=}, existed_owner=   system, request_owner={owner}")
                return jsonify({'code': 0, 'msg': 'Successfully added ID'})
            allow_until = existed.get('allow_until')
            now = datetime.now()
            if allow_until and allow_until > now:
                # 在放行窗口内，允许通过
                app.logger.info(f"addId allowed without overwrite: {excel_name=}, {sheet_name=}, {id_val=}, existed_owner={existed.get('owner')}, request_owner={owner}")
                return jsonify({'code': 0, 'msg': 'Successfully added ID'})
            else:
                fixWebsite = f"http://172.28.195.228:8008/idOp/idMgr?excelName={excel_name}&sheetName={sheet_name}&id={id_val}"
                fixWebsite = f"http://172.28.193.12:8008/idOp/idMgr?excelName={excel_name}&sheetName={sheet_name}&id={id_val}"
                historyWebsite = f"http://172.28.193.12:8008/idOp/idMgrHistory?action=add_fail&excelName={excel_name}&sheetName={sheet_name}&id={id_val}"
                _write_id_history(
                    "add_fail",
                    data.get('excelName') or "",
                    data.get('sheetName') or "",
                    data.get('id') or "",
                    data.get('owner') or "",
                    False,
                    f"permission denied, occupied by {existed.get('owner')}",
                    {"request": data, "existed": existed}
                )
                app.logger.info(f"czx addId permission denied: {existed.get('owner')=}, {owner=}")

                return jsonify(
                    {
                        'code': 1, 
                        'errMsg': f'当前ID已经被占用',
                        'errInfo': {
                            'owner': existed.get("owner"),
                            'updateAt': existed.get("updatedAt"),
                            'website': historyWebsite,
                        }
                    }
                )
        
        record = {
            "excelName": excel_name,
            "sheetName": sheet_name,
            "id": id_val,
            "level": level,
            "parentId": parent_id,
            "path": path,
            "owner": owner,
            "permissions": data.get('permissions', ["read", "write"]),
            "occupy": bool(data.get('occupy', False))
        }
        
        mongo_imp.add_id(record)
        action = "add" if not existed else "update"
        _write_id_history(action, excel_name, sheet_name, id_val, owner, True, "", {"record": record})
        app.logger.info(f"addId success: {excel_name=}, {sheet_name=}, {id_val=}, {owner=}")
        return jsonify({'code': 0, 'msg': 'Successfully added ID'})
    except Exception as e:
        app.logger.error(f"Failed to add ID: {e}")
        try:
            data = request.json or {}
            _write_id_history("add", data.get('excelName') or "", data.get('sheetName') or "", data.get('id') or "", data.get('owner') or "", False, str(e), {"request": data})
        except Exception:
            pass
        app.logger.error(f"addId failed: {e}")
        return jsonify({'code': 1, 'errMsg': str(e)})


@app.route('/deleteId', methods=['POST'])
def deleteId():
    """删除 ID"""
    try:
        data = request.json
        excel_name = data.get('excelName')
        sheet_name = data.get('sheetName')
        id_val = data.get('id')
        
        if not all([excel_name, sheet_name, id_val]):
            return jsonify({'code': 1, 'errMsg': 'Missing required fields'})
            
        mongo_imp = get_excel_id_mongo()
        success = mongo_imp.delete_id(excel_name, sheet_name, id_val)
        
        if success:
            _write_id_history("delete", excel_name, sheet_name, id_val, data.get('owner') or "", True, "", {"request": data})
            app.logger.info(f"deleteId success: {excel_name=}, {sheet_name=}, {id_val=}")
            return jsonify({'code': 0, 'msg': 'Successfully deleted ID'})
        else:
            _write_id_history("delete", excel_name, sheet_name, id_val, data.get('owner') or "", False, "ID not found", {"request": data})
            # 目前找不到也先返回0
            app.logger.info(f"deleteId failed: {excel_name=}, {sheet_name=}, {id_val=}")
            return jsonify({'code': 0, 'errMsg': 'ID not found'})
    except Exception as e:
        app.logger.error(f"Failed to delete ID: {e}")
        try:
            data = request.json or {}
            _write_id_history("delete", data.get('excelName') or "", data.get('sheetName') or "", data.get('id') or "", data.get('owner') or "", False, str(e), {"request": data})
        except Exception:
            pass
        app.logger.error(f"deleteId failed: {e}")
        return jsonify({'code': 1, 'errMsg': str(e)})


@app.route('/allowId', methods=['POST'])
def allowId():
    """让该ID在10分钟内可以提交"""
    try:
        data = request.json
        excel_name = data.get('excelName')
        sheet_name = data.get('sheetName')
        owner = data.get('owner', "system")
        id_val = data.get('id')
        if not all([excel_name, sheet_name, id_val]):
            return jsonify({'code': 1, 'errMsg': 'Missing required fields'})
        mongo_imp = get_excel_id_mongo()
        success = mongo_imp.allow_id(excel_name, sheet_name, id_val)
        if not success:
            _write_id_history("allow", excel_name, sheet_name, id_val, owner, False, "ID not found", {"request": data})
            return jsonify({'code': 1, 'errMsg': 'ID not found'})
        _write_id_history("allow", excel_name, sheet_name, id_val, owner, True, "", {"request": data})
        app.logger.info(f"allowId success: {excel_name=}, {sheet_name=}, {id_val=}")
        return jsonify({'code': 0, 'msg': 'ID allowed for 10 minutes'})
    except Exception as e:
        app.logger.error(f"allowId failed: {e}")
        try:
            data = request.json or {}
            _write_id_history("allow", data.get('excelName') or "", data.get('sheetName') or "", data.get('id') or "", data.get('owner') or "", False, str(e), {"request": data})
        except Exception:
            pass
        return jsonify({'code': 1, 'errMsg': str(e)})


@app.route('/updateId', methods=['POST'])
def updateId():
    """更新 ID 字段"""
    try:
        data = request.json
        excel_name = data.get('excelName')
        sheet_name = data.get('sheetName')
        id_val = data.get('id')
        update_fields = data.get('updateFields', {})
        owner = data.get('owner', "system")
        
        # 白名单过滤：目前仅允许更新 owner 字段
        allowed_fields = ['owner']
        filtered_fields = {k: v for k, v in update_fields.items() if k in allowed_fields}
        
        if not all([excel_name, sheet_name, id_val]):
            return jsonify({'code': 1, 'errMsg': 'Missing required fields'})
            
        if not filtered_fields:
            return jsonify({'code': 1, 'errMsg': 'No valid fields provided for update'})
            
        mongo_imp = get_excel_id_mongo()
        success = mongo_imp.update_id(excel_name, sheet_name, id_val, filtered_fields)

        _write_id_history("change_owner", excel_name, sheet_name, id_val, owner, True, "", {"request": data})
        
        if success:
            return jsonify({'code': 0, 'msg': 'Successfully updated ID'})
        else:
            return jsonify({'code': 1, 'errMsg': 'ID not found or no changes made'})
    except Exception as e:
        app.logger.error(f"Failed to update ID: {e}")
        return jsonify({'code': 1, 'errMsg': str(e)})


@app.route('/getIdInfo', methods=['POST'])
def getIdInfo():
    """获取 ID 详情"""
    try:
        data = request.json
        excel_name = data.get('excelName')
        sheet_name = data.get('sheetName')
        id_val = data.get('id')
        
        if not all([excel_name, sheet_name, id_val]):
            return jsonify({'code': 1, 'errMsg': 'Missing required fields'})
            
        mongo_imp = get_excel_id_mongo()
        info = mongo_imp.get_id_info(excel_name, sheet_name, id_val)
        
        if info:
            return jsonify({'code': 0, 'data': info})
        else:
            return jsonify({'code': 1, 'errMsg': 'ID not found'})
    except Exception as e:
        app.logger.error(f"Failed to get ID info: {e}")
        return jsonify({'code': 1, 'errMsg': str(e)})


@app.route('/listIds', methods=['POST'])
def listIds():
    """列表查询 ID"""
    try:
        data = request.json
        query = data.get('query', {})
        limit = data.get('limit', 100)
        skip = data.get('skip', 0)
        
        mongo_imp = get_excel_id_mongo()
        items = mongo_imp.list_ids(query, limit, skip)
        total = mongo_imp.count_ids(query)
        
        app.logger.info(f"List IDs: {query}, Limit: {limit}, Skip: {skip}, Total: {total}")
        
        return jsonify({
            'code': 0,
            'data': {
                'items': items,
                'total': total
            }
        })
    except Exception as e:
        app.logger.error(f"Failed to list IDs: {e}")
        return jsonify({'code': 1, 'errMsg': str(e)})


@app.route('/clearAllIds', methods=['POST'])
def clearAllIds():
    """清空所有 ID"""
    try:
        deleteAllIds()
        return jsonify({'code': 0, 'msg': 'Successfully cleared all IDs'})
    except Exception as e:
        app.logger.error(f"Failed to clear all IDs: {e}")
        return jsonify({'code': 1, 'errMsg': str(e)})


@app.route('/listExcels', methods=['POST'])
def listExcels():
    """列出所有 Excel"""
    try:
        mongo_imp = get_excel_id_mongo()
        excels = mongo_imp.list_excels()
        return jsonify({'code': 0, 'data': excels})
    except Exception as e:
        app.logger.error(f"Failed to list excels: {e}")
        return jsonify({'code': 1, 'errMsg': str(e)})


@app.route('/listSheets', methods=['POST'])
def listSheets():
    """列出指定 Excel 的所有 Sheet"""
    try:
        data = request.json
        excel_name = data.get('excelName')
        if not excel_name:
            return jsonify({'code': 1, 'errMsg': 'Missing excelName'})
            
        mongo_imp = get_excel_id_mongo()
        sheets = mongo_imp.list_sheets(excel_name)
        return jsonify({'code': 0, 'data': sheets})
    except Exception as e:
        app.logger.error(f"Failed to list sheets: {e}")
        return jsonify({'code': 1, 'errMsg': str(e)})


def deleteAllIds():
    """删除所有 ID"""
    mongo_imp = get_excel_id_mongo()
    try:
        mongo_imp.collection.drop()
    finally:
        mongo_imp.collection = mongo_imp.get_collection(mongo_imp.COLLECTION_NAME)
        mongo_imp._ensure_indexes()


# 导出测试数据后最终数据库中的典型结构如下：
''' 
mongos> db.excel_ids.findOne()
{
        "_id" : ObjectId("69d1c3826b4b2c1301213126"),
        "excelName" : "BattleBot_机器人",
        "id" : "10001-1200001-1",
        "sheetName" : "AbilityTemplate_能力",
        "createdAt" : ISODate("2026-04-05T02:05:53.995Z"),
        "level" : "MainSubMinor",
        "owner" : "system",
        "parentId" : "10001-1200001",
        "path" : [
                "10001",
                "1200001",
                "1"
        ],
        "permissions" : [
                "read",
                "write"
        ],
        "updatedAt" : ISODate("2026-04-05T02:05:53.995Z")
}
'''


def importTestData():
    """初始化测试数据逻辑"""
    p4_dir = "//C7/Development/Mainline/Design/Tool/ExcelToLua/IdMgr"
    local_base_dir = config.P4_WORKSPACE_DIRECTORY
    updated_count = p4Utils.update_dir(p4_dir, local_base_dir, force=True)
    app.logger.info(f"IdMgr importTestData: updated {updated_count} files from {p4_dir}")

    data_dir = os.path.join(local_base_dir, p4_dir.replace("//", ""))
    if not os.path.exists(data_dir):
        app.logger.error(f"IdMgr directory not found after p4 update: {data_dir}")
        return 0

    mongo_imp = get_excel_id_mongo()
    all_records = []
    total_count = 0

    tsv_files = []
    for root, _, files in os.walk(data_dir):
        for filename in files:
            if filename.endswith("__ids.tsv"):
                tsv_files.append(os.path.join(root, filename))
    tsv_files.sort()
    total_files = len(tsv_files)
    app.logger.info(f"IdMgr importTestData: start import files={total_files}")
    
    for file_index, file_path in enumerate(tsv_files, start=1):
        filename = os.path.basename(file_path)
        percent = (file_index / total_files * 100.0) if total_files else 100.0
        rel_path = os.path.relpath(file_path, data_dir).replace("\\", "/")
        app.logger.info(f"IdMgr importTestData: [{file_index}/{total_files}] {percent:.2f}% file={rel_path} imported={total_count}")
            
        parts = filename.split("__")
        if len(parts) < 3:
            app.logger.error(f"Invalid filename format: {filename}")
            continue
            
        excel_name = parts[0]
        sheet_name = parts[1]
        
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
            if not lines:
                app.logger.error(f"Empty file: {filename}")
                continue
                
            level = lines[0].strip() # MainKey | MainSub | MainSubMinor
            
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    app.logger.error(f"Empty line in {filename}: {line}")
                    continue
                    
                id_parts = line.split('\t')
                full_id = ""
                parent_id = None
                path = []
                
                if level == "MainKey":
                    full_id = id_parts[0]
                    parent_id = None
                    path = [full_id]
                elif level == "MainSub":
                    if len(id_parts) >= 2:
                        main_key = id_parts[0]
                        sub_key = id_parts[1]
                        
                        if sub_key.startswith(f"{main_key}-"):
                            sub_key_clean = sub_key[len(main_key)+1:]
                            full_id = sub_key
                        else:
                            sub_key_clean = sub_key
                            full_id = f"{main_key}-{sub_key}"
                        
                        parent_id = main_key
                        path = [main_key, sub_key_clean]
                elif level == "MainSubMinor":
                    if len(id_parts) >= 3:
                        main_key = id_parts[0]
                        sub_key = id_parts[1]
                        minor_key = id_parts[2]
                        
                        if sub_key.startswith(f"{main_key}-"):
                            sub_key_full = sub_key
                            sub_key_clean = sub_key[len(main_key)+1:]
                        else:
                            sub_key_full = f"{main_key}-{sub_key}"
                            sub_key_clean = sub_key
                        
                        if minor_key.startswith(f"{sub_key_full}-"):
                            minor_key_clean = minor_key[len(sub_key_full)+1:]
                            full_id = minor_key
                        else:
                            minor_key_clean = minor_key
                            full_id = f"{sub_key_full}-{minor_key}"
                            
                        parent_id = sub_key_full
                        path = [main_key, sub_key_clean, minor_key_clean]
                
                if not full_id:
                    app.logger.error(f"Invalid ID format in {filename}: {line}")
                    continue
                    
                record = {
                    "excelName": excel_name,
                    "sheetName": sheet_name,
                    "id": full_id,
                    "level": level,
                    "parentId": parent_id,
                    "path": path,
                    "owner": "system",
                    "permissions": ["read", "write"]
                }
                all_records.append(record)
                total_count += 1
                
                if len(all_records) >= 500:
                    mongo_imp.bulk_save_ids(all_records)
                    all_records = []
                    
    if all_records:
        mongo_imp.bulk_save_ids(all_records)
        
    app.logger.info(f"IdMgr importTestData: done files={total_files} imported={total_count}")
    return total_count
