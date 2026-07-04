import traceback
from bson import BSON
from bson.errors import InvalidBSON
from bson.raw_bson import RawBSONDocument
from bson.codec_options import CodecOptions
from Implement.pickImpl.script.log import print_error, print_warn, print_info
import bson.json_util as json_util 
import json
import tarfile
import tempfile
import os
from pymongo import UpdateOne

import base64

# 每个账号下最多有6个角色
MAX_AVATAR_COUNT_IN_ACCOUNT = 6

# mongoDB 数据表名
COLLECTION_ACCOUNT_NAME = "Account"
COLLECTION_AVATAR_NAME = "AvatarActor"
COLLECTION_HOMELAND_NAME = "homeland_building"
COLLECTION_AVATAR_BASIC_NAME = "player_basic_info"
COLLECTION_FRIENDSHIP_NAME = "friendship_data"
COLLECTION_MAIL_NAME = "mail"
COLLECTION_OFFLINE_FRI_SYS_MSG = "offline_fri_sys_msg"
COLLECTION_QUEST_PLANE_ARCHIVE = "quest_plane_archive"
COLLECTION_OFFLINE_UNREAD_MSG = "offline_unread_msg"
COLLECTION_APPEARANCE_LOTTERY_RECORD = "appearance_lottery_record"
COLLECTION_DUNGEON_AUCTION_ORDER = "dungeon_auction_order"
COLLECTION_MAIL_FAVORITES = "mail_favorites"
COLLECTION_TEAM_3V3_BRIEF_RECORD_TABLE = "team_3v3_brief_record_table"
COLLECTION_TEAM_12V12_BRIEF_RECORD_TABLE = "team_12v12_brief_record_table"
COLLECTION_TEAM_6V6_BRIEF_RECORD_TABLE = "team_6v6_brief_record_table"
COLLECTION_PVP_CHAMPION_BRIEF_RECORD_TABLE = "pvp_champion_brief_record_table"
COLLECTION_GUILD_BID_RECORD_TABLE = "guild_bid_record_table"
COLLECTION_WORLD_BID_RECORD_TABLE = "world_bid_record_table"
COLLECTION_RED_PACKET_RECORD = "red_packet_record"
COLLECTION_UMSG = "umsg"
COLLECTION_CHAT_CUSTOM_IMG = "chat_custom_img"
COLLECTION_FELLOW_GACHA_RECORDS = "fellow_gacha_records"
COLLECTION_PAY_ORDER = "pay_order"
COLLECTION_COMMONINTERACTOR_PRIVATE_STATE = "commonInteractor_private_state"

# ===== 查找角色的账号 =====
def getAccountByAvatarID(db, avatarIDList):
    collection_avatar = db[COLLECTION_AVATAR_NAME]
    docs = collection_avatar.find({"_id":{"$in":avatarIDList}}, {"_id":1, "accountID":1})
    if docs:
        return docs
    
# ===== 根据玩家名字查找角色ID =====
def getAvatarIDListByName(db, avatarNameList):
    collection_avatar = db[COLLECTION_AVATAR_NAME]
    docs = collection_avatar.find({"Name":{"$in":avatarNameList}}, {"_id":1, "Name":1})
    if docs:
        return [ doc["_id"] for doc in docs]


# ===== 查找账号下的所有角色 =====
def getAvatarListForAccount(db, accountID):
    collection_account = db[COLLECTION_ACCOUNT_NAME]
    doc = collection_account.find_one({"accountID":accountID}, {"_id":0, "accountID":1, "roleIds":1})
    if doc:
        return doc["roleIds"]
    

def updateDocsField(docs, name, value):
    result_docs = []
    for doc in docs:
        try:
            doc = BSON(doc.raw).decode()
            if name in doc:
                doc[name] = value
            result_docs.append(doc)

        except Exception as e:
            print_warn(f"update docs field error: {e}")

    return result_docs
    
    
# ===== 导入指定collection的数据 =====
def collectionNeedFieldID(collection_config, collection_name):
    if collection_name not in collection_config:
        return False
    elif "shard_key" not in collection_config[collection_name]:
        return False
    else:
        return "_id" in collection_config[collection_name]["shard_key"]
    

def importCollection(src_db, dst_db, collection_name, query, projection, colleciton_config, logic_server_id):
    src_collection = src_db[collection_name]
    dst_collection = dst_db[collection_name]

    if collectionNeedFieldID(colleciton_config, collection_name):
        docs = src_collection.find(query, projection)
    else:
        projection["_id"] = 0
        docs = src_collection.find(query, projection)
    if not docs:
        print_warn(f"importCollection: {collection_name} 没有找到")
        return True

    # 修改LogicServerID
    result_docs = updateDocsField(docs, "LogicServerID", logic_server_id)
    if len(result_docs) <= 0:
        print_warn(f"importCollection: {collection_name} 没有找到")
        return True

    # 先清空目标collection
    dst_collection.delete_many({})

    # 再导入数据
    result = dst_collection.insert_many(result_docs)
    print(f"{collection_name} 导入成功, {len(result.inserted_ids)}条")

    return True


def importCollections(src_db, dst_db, collections, collection_config, logic_server_id):
    projection = {"LogicServerID":0}
    for name, query in collections.items():
        importCollection(src_db, dst_db, name, query, projection, collection_config, logic_server_id)

    return True
        

# ===== 导入指定service数据 =====
def serviceIsShared(service_config, service_name):
    if service_name not in service_config:
        return False
    elif "logic_server_shared" not in service_config[service_name]:
        return False
    else:
        return service_config[service_name]["logic_server_shared"]
    

def importService(src_db, dst_db, service_name, service_config):
    projection = {"_id":0, "_entity_type":0, "_term":0, "_term_index":0, "LogicServerID":0}

    shard_cnt = service_config["shard_cnt"]
    for shard_index in range(0, shard_cnt):
        doc = src_db[service_name].find_one({"shardIndex":shard_index}, projection)
        if not doc:
            print_error(f"{service_name} shardIndex:{shard_index} 不存在")
            return False
        else:
            dst_db[service_name].update_one({"shardIndex":shard_index}, {"$set":doc}, upsert=True)

    print(f"{service_name} 导入成功")
    return True


def importServices(src_db, src_shared_db, dst_db, dst_shared_db, serviceList, service_config):
    for name in serviceList:
        if name not in service_config:
            print_error(f"service {name} 无效")
            continue

        if serviceIsShared(service_config, name):
            if not importService(src_shared_db, dst_shared_db, name, service_config[name]):
                return False
        else:
            if not importService(src_db, dst_db, name, service_config[name]):
                return False
            
        # 导入depend_service数据
        if "boot_depend_services" in service_config[name]:
            for depend_service in service_config[name]["boot_depend_services"]:
                if serviceIsShared(service_config, depend_service):
                    importService(src_shared_db, dst_shared_db, depend_service, service_config[depend_service])
                else:
                    importService(src_db, dst_db, depend_service, service_config[depend_service])

    return True
        

# ===== 直接把指定账号和角色数据导入到dst_db中 =====
def importAccountData(dst_db, accountID, avatarIDList):
    doc = {
        "accountID": accountID,
        "CreatingRole": [],
        "roleIds": avatarIDList
    }

    # 先删除
    dst_db[COLLECTION_ACCOUNT_NAME].delete_one({"accountID":accountID})

    dst_db[COLLECTION_ACCOUNT_NAME].insert_one(doc)
    return True


# ===== 角色数据所需的表 =====
AVATAR_DATA_COLLECTION_INFO = {
    COLLECTION_AVATAR_NAME:{"key": "_id", "replace_account":True},
    COLLECTION_FRIENDSHIP_NAME:{"key": "roleID"},
    COLLECTION_MAIL_NAME:{"key": "receiver"},
    COLLECTION_OFFLINE_FRI_SYS_MSG:{"key": "id"},
    COLLECTION_QUEST_PLANE_ARCHIVE:{"key": "roleID"},
    COLLECTION_OFFLINE_UNREAD_MSG:{"key": "roleID"},
    COLLECTION_APPEARANCE_LOTTERY_RECORD:{ "key": "roleID"},
    COLLECTION_DUNGEON_AUCTION_ORDER:{"key": "_id"},
    COLLECTION_MAIL_FAVORITES:{"key":"uid"},
    COLLECTION_TEAM_3V3_BRIEF_RECORD_TABLE:{"key":"AvatarActorId"},
    COLLECTION_TEAM_12V12_BRIEF_RECORD_TABLE:{"key":"AvatarActorId"},
    COLLECTION_TEAM_6V6_BRIEF_RECORD_TABLE:{"key":"AvatarActorId"},
    COLLECTION_PVP_CHAMPION_BRIEF_RECORD_TABLE:{"key":"AvatarActorId"},
    COLLECTION_GUILD_BID_RECORD_TABLE:{"key":"AvatarActorId"},
    COLLECTION_WORLD_BID_RECORD_TABLE:{"key":"AvatarActorId"},
    COLLECTION_RED_PACKET_RECORD:{"key":"avatarID"},
    COLLECTION_UMSG:{"key":"avatarID"},
    COLLECTION_CHAT_CUSTOM_IMG:{"key":"uid"},
    COLLECTION_FELLOW_GACHA_RECORDS:{"key":"avatarID"},
    COLLECTION_PAY_ORDER:{"key":"roleID"},
    COLLECTION_COMMONINTERACTOR_PRIVATE_STATE:{"key":"avatarID"}
}

# ===== 导入角色数据 =====
def importDataByAvatarID(src_db, dst_db, avatarIDList, dest_account = ""):
    for collection_name, info in AVATAR_DATA_COLLECTION_INFO.items():
        print(f"开始导入{collection_name}数据...")
        src_collection = src_db[collection_name]
        dst_collection = dst_db[collection_name]

        projection = None
        if info["key"] != "_id":
            # 防止_id重复
            projection = {"_id":0}

        filter = {info["key"]:{"$in":avatarIDList}}

        if projection:
            docs = src_collection.find(filter, projection)
        else:
            docs = src_collection.find(filter)

        raw_docs = []
        for raw_doc in docs:
            raw_docs.append(raw_doc)
        if len(raw_docs) <= 0:
            print_warn(f"importDataByAvatarID: {collection_name}中没有对应数据")
            continue

        dst_collection.delete_many(filter)
        dst_collection.insert_many(raw_docs)
        
        # 替换账号
        if ("replace_account" in info) and info["replace_account"] and dest_account != "":
            dst_collection.update_many(filter, {"$set":{"accountID":dest_account}})

    return True

# ===== 导入指定账号的所有角色数据 =====
def importAvatarDataByAccount(src_db, dst_db, accountIDList):
    filter = {"accountID":{"$in":accountIDList}}
    docs = list(src_db[COLLECTION_ACCOUNT_NAME].find(filter, {"_id":0}))
    if not docs:
        print_error(f"importAvatarDataByAccount: 账号数据没有找到")
        traceback.print_stack()
        return False
    
    dst_db[COLLECTION_ACCOUNT_NAME].delete_many(filter)
    dst_db[COLLECTION_ACCOUNT_NAME].insert_many(docs)

    avatarIDList = [ avatarID for doc in docs for avatarID in doc["roleIds"]]
    if not importDataByAvatarID(src_db, dst_db, avatarIDList):
        return False

    return True

# ===== 导入指定角色名的角色数据 =====
def importAvatarDataByAvatarID(src_db, dst_db, avatarIDList, dest_account):
    docs = list(src_db[COLLECTION_AVATAR_NAME].find({"_id":{"$in":avatarIDList}}, {"_id":1, "accountID":1, "Name":1}))
    if not docs:
        print_error(f"importAvatarDataByAvatarID: 角色数据没有找到")
        traceback.print_stack()
        return False
    
    avatarIDList = [doc["_id"] for doc in docs][:MAX_AVATAR_COUNT_IN_ACCOUNT]
    print_info(f"角色列表:{avatarIDList}")

    if not importAccountData(dst_db, dest_account, avatarIDList):
        return False
    if not importDataByAvatarID(src_db, dst_db, avatarIDList, dest_account):
        return False
    
    return True


# ===== 导入指定角色名的角色数据 =====
def importAvatarDataByAvatarName(src_db, dst_db, avatarNameList, dest_account):
    docs = list(src_db[COLLECTION_AVATAR_NAME].find({"Name":{"$in":avatarNameList}}, {"_id":1, "accountID":1, "Name":1}))
    if not docs:
        print_error(f"importAvatarDataByAvatarName: 角色数据没有找到")
        traceback.print_stack()
        return False
    
    avatarIDList = [doc["_id"] for doc in docs][:MAX_AVATAR_COUNT_IN_ACCOUNT]
    print_info(f"角色列表:{avatarIDList}")

    if not importAccountData(dst_db, dest_account, avatarIDList):
        return False
    if not importDataByAvatarID(src_db, dst_db, avatarIDList, dest_account):
        return False
    
    return True


# ===== 导入指定角色名/ID的角色数据 =====
def importAvatarDataByNameOrID(src_db, dst_db, avatarNameList, avatarIDList, dest_account):
    docs = list(src_db[COLLECTION_AVATAR_NAME].find({
        "$or":[
            {"_id":{"$in":avatarIDList}},
            {"Name":{"$in":avatarNameList}}
        ]
    }, {"_id":1, "accountID":1, "Name":1}))

    if not docs:
        print_error(f"importAvatarDataByAvatarName: 角色数据没有找到")
        traceback.print_stack()
        return False
    
    avatarIDList = [doc["_id"] for doc in docs][:MAX_AVATAR_COUNT_IN_ACCOUNT]
    print_info(f"角色列表:{avatarIDList}")

    if not importAccountData(dst_db, dest_account, avatarIDList):
        return False
    if not importDataByAvatarID(src_db, dst_db, avatarIDList, dest_account):
        return False

    return True

# ====== 新增：导出/恢复 功能 ======
def dump_to_file(src_db, conf, service_config, dump_file_path):
    """将 conf 指定的数据导出到文件（bson.json_util 格式）"""
    os.makedirs(os.path.dirname(dump_file_path), exist_ok=True)

    # 导出 Account
    import_account = conf.get("Account", [])
    if import_account:
        try:
            for doc in src_db[COLLECTION_ACCOUNT_NAME].find({"accountID": {"$in": import_account}}, {"_id": 0}):
                bson_data = doc.raw
                file_name = f'Account_{import_account}' + ".bson"
                filepath = os.path.join(dump_file_path, file_name)
                with open(filepath, 'wb') as f:
                    f.write(bson_data)
        except Exception as e:
            print_warn(f"Account collection 查询错误: {e}")
    # else:
    #     print_warn(f"Account collection 未指定导出账号")

    short_uids = conf.get("ShortUID", [])
    avatar_ids = conf.get("AvatarID", [])
    if short_uids:
        short_uids = [int(uid) for uid in short_uids if uid]
        try:
            for doc in src_db[COLLECTION_AVATAR_NAME].find({"shortUid": {"$in": short_uids}}, {"_id": 1}):
                avatar_ids.append(doc["_id"])
        except Exception as e:
            print_warn(f"ShortUID collection 查询错误: {e}")

    # 导出 Avatar 列表（按 ID 或 Name）
    
    avatar_names = conf.get("AvatarName", [])
    avatar_id_list = []
    if avatar_ids:
        avatar_id_list.extend(avatar_ids)
    # if avatar_names:
    #     docs = []
    #     try:
    #         for doc in src_db[COLLECTION_AVATAR_NAME].find({"Name": {"$in": avatar_names}}, {"_id": 1}):
    #             bson_data = BSON.encode(doc)
    #             file_name = f'Account_{doc["accountID"]}' + ".bson"
    #             filepath = os.path.join(dump_file_path, file_name)
    #             with open(filepath, 'wb') as f:
    #                 f.write(bson_data)
    #     except Exception as e:
    #         print_warn(f"AvatarActor collection 查询错误: {e}")
    #     avatar_id_list.extend([d["_id"] for d in docs if "_id" in d])
    # data["AvatarIDList"] = avatar_id_list

    # 导出 Avatar 相关的 collection 数据
    if avatar_id_list:
        for coll_name, info in AVATAR_DATA_COLLECTION_INFO.items():
            key = info.get("key")
            if key:
                try:
                    for avatar_id in avatar_id_list:
                        docs = src_db[coll_name].find({key: avatar_id})
                        for doc in docs:
                            bson_data = doc.raw
                            # 直接使用 avatar_id，不访问 doc[key]
                            file_name = f'{coll_name}_#_{avatar_id}' + ".bson"
                            filepath = os.path.join(dump_file_path, file_name)
                            with open(filepath, 'wb') as f:
                                f.write(bson_data)
                except Exception as e:
                    print_warn(f"{coll_name} collection 查询错误: {e}")

    print_info(f"dump 写入: {dump_file_path}")
    return True
    

def restore_from_file(dst_db, dump_file_path, dest_account="test", regen_avatar_id=False):
    """
    从 dump 文件夹恢复数据到目标 db。
    每个 BSON 文件对应一个文档，文件名格式为 {collection}_{key}.bson

    regen_avatar_id用于重新生成avatarID
    """
    try:
        if not os.path.isdir(dump_file_path):
            print_error(f"restore_from_file: 路径不是目录 {dump_file_path}")
            return False

        # 收集所有 .bson 文件
        bson_files = [f for f in os.listdir(dump_file_path) if f.endswith('.bson')]
        if not bson_files:
            print_warn(f"restore_from_file: 目录中没有 .bson 文件")
            return False

        # 按集合分组文件
        collection_files = {}
        avatar_ids_restored = set()
        for filename in bson_files:
            # 解析文件名：{coll_name}_{key}.bson
            parts = filename[:-5].rsplit('_#_', 1)  # 去掉 .bson 后缀，分割第一个下划线
            if len(parts) < 2:
                print_warn(f"restore_from_file: 文件名格式错误 {filename}")
                continue
            coll_name = parts[0]
            key_value = parts[1]

            if coll_name not in collection_files:
                collection_files[coll_name] = []
            collection_files[coll_name].append(filename)

            if coll_name == COLLECTION_AVATAR_NAME:
                print_info(f"找到 AvatarActor 角色ID: {key_value}")
                avatar_ids_restored.add(key_value)

        avatar_ids = list(avatar_ids_restored)
        # 恢复 Account 集合
        if dest_account:
            account_doc = {"accountID": dest_account, "CreatingRole": [], "roleIds": avatar_ids}
            dst_db[COLLECTION_ACCOUNT_NAME].delete_one({"accountID": dest_account})
            dst_db[COLLECTION_ACCOUNT_NAME].insert_one(account_doc)

        # 恢复其他 Avatar 相关集合
        for coll_name, info in AVATAR_DATA_COLLECTION_INFO.items():
            coll_files = collection_files.get(coll_name, [])
            if not coll_files:
                continue
            
            key = info.get("key", "_id")
            
            # 批量删除旧数据
            dst_db[coll_name].delete_many({key: {"$in": avatar_ids}})

            # 逐个插入新数据
            for filename in coll_files:
                filepath = os.path.join(dump_file_path, filename)
                try:
                    with open(filepath, "rb") as f:
                        data_bson = f.read()
                    doc = RawBSONDocument(data_bson)
                    
                    dst_db[coll_name].insert_one(doc)
                    # 替换 accountID
                    if info.get("replace_account") and dest_account:
                        dst_db[coll_name].update_many(
                            {key: {"$in": avatar_ids}},
                            {"$set": {"accountID": dest_account}}
                        )
                    print_info(f"恢复 {coll_name}: {filename}")
                except Exception as e:
                    print_warn(f"恢复 {coll_name} 失败 {filename}: {e}")

        # 如果需要重新生成 AvatarID：在数据按原样插入完成后，再从库内取出本次插入的ID并做替换
        if regen_avatar_id and avatar_ids:
            try:
                import random
                import string

                _ALNUM = string.ascii_letters + string.digits

                def gen_new_avatar_id(old_id: str) -> str:
                    """avatarid 字母/数字混用：把旧 avatarid 的后6位替换为随机数字或字母。

                    - 若 old_id 长度 >= 6：new_id = old_id[:-6] + random_alnum(6)
                    - 若 old_id 长度 < 6：new_id = old_id + random_alnum(6-len(old_id))（尽量保持原ID可读）
                    """
                    if not old_id:
                        return ''.join(random.choices(_ALNUM, k=6))
                    if len(old_id) >= 6:
                        return old_id[:-6] + ''.join(random.choices(_ALNUM, k=6))
                    return old_id + ''.join(random.choices(_ALNUM, k=6 - len(old_id)))

                # 1) 从库内取出本次插入的 AvatarActor 列表（以 dump 文件中的 avatar_ids 作为筛选）
                inserted_avatar_ids = list(dst_db[COLLECTION_AVATAR_NAME].distinct('_id', {"_id": {"$in": avatar_ids}}))
                inserted_avatar_ids = [str(x) for x in inserted_avatar_ids]

                avatar_id_map = {}
                used_new = set(inserted_avatar_ids)
                for old in inserted_avatar_ids:
                    # 确保生成不重复
                    for _ in range(50):
                        new_id = gen_new_avatar_id(old)
                        if new_id != old and new_id not in used_new:
                            avatar_id_map[old] = new_id
                            used_new.add(new_id)
                            break

                if not avatar_id_map:
                    print_warn("regen_avatar_id=True 但未生成任何ID映射（可能没有匹配到 AvatarActor）")
                else:
                    print_info(f"regen_avatar_id: 生成 {len(avatar_id_map)} 个 AvatarID 映射")

                    # 2) 先更新所有引用字段（除 AvatarActor 自身）
                    # for coll_name, info in AVATAR_DATA_COLLECTION_INFO.items():
                    #     if coll_name == COLLECTION_AVATAR_NAME:
                    #         continue
                    #     key = info.get('key', '_id')
                    #     for old_id, new_id in avatar_id_map.items():
                    #         dst_db[coll_name].update_many({key: old_id}, {'$set': {key: new_id}})
                    
                    for coll_name, info in AVATAR_DATA_COLLECTION_INFO.items():
                        if coll_name == COLLECTION_AVATAR_NAME:
                            continue
                        key = info.get('key', '_id')
                        bulk_ops = []
                        for old_id, new_id in avatar_id_map.items():
                            doc_ids = list(dst_db[coll_name].find({key: old_id}, {'_id': 1}))
                            for doc in doc_ids:
                                bulk_ops.append(
                                    UpdateOne(
                                        {'_id': doc['_id'], key: old_id},
                                        {'$set': {key: new_id}}
                                    )
                                )
                        if bulk_ops:
                            dst_db[coll_name].bulk_write(bulk_ops, ordered=False)

                    # 3) 再更新 AvatarActor 自身：避免客户端解码（非UTF-8风险），使用 MongoDB 端聚合复制并改 _id
                    #    逻辑：match old_id -> set _id=new_id -> merge into same collection (insert) -> delete old
                    for old_id, new_id in avatar_id_map.items():
                        try:
                            dst_db[COLLECTION_AVATAR_NAME].aggregate([
                                {'$match': {'_id': old_id}},
                                {'$set': {'_id': new_id}},
                                {'$merge': {'into': COLLECTION_AVATAR_NAME, 'on': '_id', 'whenMatched': 'fail', 'whenNotMatched': 'insert'}}
                            ])
                            dst_db[COLLECTION_AVATAR_NAME].delete_one({'_id': old_id})
                        except Exception as e:
                            print_warn(f"AvatarActor _id 迁移失败 {old_id} -> {new_id}: {e}")

                    # 4) 更新 Account.roleIds
                    if dest_account:
                        # 先从 roleIds 中删除所有旧的 avatarid
                        dst_db[COLLECTION_ACCOUNT_NAME].update_one(
                            {"accountID": dest_account},
                            {"$pull": {"roleIds": {"$in": list(avatar_id_map.keys())}}},
                        )
                        # 再添加新的 avatarid（使用 addToSet 避免重复）
                        dst_db[COLLECTION_ACCOUNT_NAME].update_one(
                            {"accountID": dest_account},
                            {"$addToSet": {"roleIds": {"$each": list(avatar_id_map.values())}}},
                            upsert=True
                        )

            except Exception as e:
                print_warn(f"regen_avatar_id 处理失败: {e}")

        print_info(f"从 {dump_file_path} 恢复完成")
        return True
    except Exception as e:
        print_error(f"restore_from_file 错误: {e}")
        traceback.print_exc()
        return False