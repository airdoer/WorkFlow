#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, OperationFailure
from bson import ObjectId
import config
from managers import timeMgr

logger = logging.getLogger(__name__)


class MongoImp:
    """MongoDB操作实现类"""
    
    def __init__(self, connection_string: str = None, database_name: str = None):
        """
        初始化MongoDB连接
        
        Args:
            connection_string: MongoDB连接字符串，如果为None则使用config.py中的配置
            database_name: 数据库名称，如果为None则使用config.py中的配置
        """
        if connection_string:
            self.connection_string = connection_string
        else:
            # 使用config.py中的配置构建连接字符串
            if hasattr(config, 'mongo_user') and hasattr(config, 'mongo_password'):
                # 带认证的连接字符串
                self.connection_string = f"mongodb://{config.mongo_user}:{config.mongo_password}@{config.mongo_host}:{config.mongo_port}/"
            else:
                # 不带认证的连接字符串
                self.connection_string = f"mongodb://{config.mongo_host}:{config.mongo_port}/"
        
        self.database_name = database_name or getattr(config, 'mongo_db', 'work_flow')
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None
        self._connect()
    
    def _connect(self):
        """建立MongoDB连接"""
        try:
            self.client = MongoClient(
                self.connection_string,
                serverSelectionTimeoutMS=5000,  # 5秒超时
                connectTimeoutMS=10000,         # 10秒连接超时
                socketTimeoutMS=20000,          # 20秒socket超时
                maxPoolSize=50,                 # 最大连接池大小
                retryWrites=True
            )
            
            # 测试连接
            self.client.admin.command('ping')
            self.db = self.client[self.database_name]
            logger.info(f"Successfully connected to MongoDB: {self.database_name}")
            
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}")
            raise
    
    def get_collection(self, collection_name: str) -> Collection:
        """获取集合对象"""
        if self.db is None:
            raise RuntimeError("Database connection not established")
        return self.db[collection_name]
    
    def close(self):
        """关闭数据库连接"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")


# region hotfixMongoImp

class HotfixMongoImp(MongoImp):
    """Hotfix相关的MongoDB操作类"""
    
    COLLECTION_NAME = "hotfix_records"
    
    def __init__(self, connection_string: str = None, database_name: str = "work_flow"):
        super().__init__(connection_string, database_name)
        self.collection = self.get_collection(self.COLLECTION_NAME)
    
    def save_hotfix_record(self, username: str, file_pairs: List[Dict], hotfix_content: str,
                          tags: List[str] = None, additional_info: Dict = None) -> str:
        """
        保存Hotfix记录
        
        Args:
            username: 用户名
            file_pairs: 文件对列表，格式: [
                {
                    "raw_file_name": "path", 
                    "old_file": "path1", 
                    "new_file": "path2",
                    "old_file_content": "文件内容(可选)",
                    "new_file_content": "文件内容(可选)"
                }, ...
            ]
            hotfix_content: Hotfix内容
            tags: Hotfix类型标签列表，如 ['flowchart', 'excel']
            additional_info: 额外信息
            
        Returns:
            str: 插入记录的ObjectId字符串
        """
        try:
            record = {
                "username": username,
                "file_pairs": file_pairs,
                "hotfix_content": hotfix_content,
                "tags": tags or [],
                "created_at": timeMgr.getCurrentDateTime(),
                "updated_at": timeMgr.getCurrentDateTime(),
                "additional_info": additional_info or {}
            }
            
            result = self.collection.insert_one(record)
            logger.info(f"Hotfix record saved with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Failed to save hotfix record: {e}")
            raise
    
    def find_hotfix_records(self, username: str = None, start_time: datetime = None, 
                           end_time: datetime = None, file_name: str = None, remark: str = None, record_id: str = None,
                           tags: List[str] = None,
                           limit: int = 100, skip: int = 0) -> List[Dict]:
        """
        查询Hotfix记录
        
        Args:
            username: 用户名过滤
            start_time: 开始时间
            end_time: 结束时间
            file_name: 文件名过滤（模糊匹配）
            remark: 备注过滤（模糊匹配）
            record_id: 记录ID
            limit: 返回记录数限制
            skip: 跳过记录数
            
        Returns:
            List[Dict]: 查询结果列表
        """
        try:
            query = {}
            
            # 记录ID过滤
            if record_id:
                try:
                    query["_id"] = ObjectId(record_id)
                except Exception:
                    # 如果record_id不是有效的ObjectId格式，则尝试作为字符串匹配（虽然通常是ObjectId）
                    # 或者直接返回空列表，因为ID格式不对肯定查不到
                    logger.warning(f"Invalid ObjectId format: {record_id}")
                    return []
            
            # 用户名过滤
            if username:
                query["username"] = username
            
            # 时间范围过滤
            if start_time or end_time:
                time_query = {}
                if start_time:
                    time_query["$gte"] = start_time
                if end_time:
                    time_query["$lte"] = end_time
                query["created_at"] = time_query
            
            # 构建复杂查询条件
            and_conditions = []

            # 文件名过滤
            if file_name:
                and_conditions.append({
                    "$or": [
                        {"file_pairs.old_file": {"$regex": file_name, "$options": "i"}},
                        {"file_pairs.new_file": {"$regex": file_name, "$options": "i"}}
                    ]
                })
            
            # 备注过滤
            if remark:
                and_conditions.append({
                    "$or": [
                        {"additional_info": {"$regex": remark, "$options": "i"}},
                        {"additional_info.remark": {"$regex": remark, "$options": "i"}}
                    ]
                })
            
            # tags 过滤（支持精确匹配和正则匹配）
            if tags:
                # 如果tag包含正则特殊字符（如 .* ? [ ]），使用$elemMatch + $regex
                # 否则使用精确匹配 $in
                tag_conditions = []
                for tag in tags:
                    # 检测是否包含正则特殊字符
                    if any(char in tag for char in ['.*', '.+', '?', '[', ']', '^', '$', '(', ')']):
                        # 正则匹配：tags数组中任意元素匹配该正则
                        tag_conditions.append({"tags": {"$elemMatch": {"$regex": tag, "$options": "i"}}})
                    else:
                        # 精确匹配
                        tag_conditions.append({"tags": tag})
                
                if len(tag_conditions) == 1:
                    query.update(tag_conditions[0])
                else:
                    # 多个tag条件，OR关系
                    query["$or"] = tag_conditions
            
            if and_conditions:
                query["$and"] = and_conditions
            
            # 执行查询
            total_count = self.collection.count_documents(query)
            cursor = self.collection.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
            
            results = []
            for doc in cursor:
                # 转换ObjectId为字符串
                doc["_id"] = str(doc["_id"])
                # 转换datetime为ISO格式字符串
                if "created_at" in doc:
                    doc["created_at"] = doc["created_at"].isoformat()
                if "updated_at" in doc:
                    doc["updated_at"] = doc["updated_at"].isoformat()
                results.append(doc)
            
            logger.info(f"Found {len(results)} hotfix records (total: {total_count})")
            return results, total_count
            
        except Exception as e:
            logger.error(f"Failed to find hotfix records: {e}")
            raise
    
    def get_hotfix_record_by_id(self, record_id: str) -> Optional[Dict]:
        """
        根据ID获取Hotfix记录
        
        Args:
            record_id: 记录ID
            
        Returns:
            Optional[Dict]: 记录详情或None
        """
        try:
            doc = self.collection.find_one({"_id": ObjectId(record_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
                if "created_at" in doc:
                    doc["created_at"] = doc["created_at"].isoformat()
                if "updated_at" in doc:
                    doc["updated_at"] = doc["updated_at"].isoformat()
            return doc
            
        except Exception as e:
            logger.error(f"Failed to get hotfix record by ID {record_id}: {e}")
            raise
    
    def update_hotfix_record(self, record_id: str, update_data: Dict) -> bool:
        """
        更新Hotfix记录
        
        Args:
            record_id: 记录ID
            update_data: 更新数据
            
        Returns:
            bool: 是否更新成功
        """
        try:
            update_data["updated_at"] = datetime.now(timezone.utc)
            result = self.collection.update_one(
                {"_id": ObjectId(record_id)},
                {"$set": update_data}
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to update hotfix record {record_id}: {e}")
            raise
    
    def delete_hotfix_record(self, record_id: str) -> bool:
        """
        删除Hotfix记录
        
        Args:
            record_id: 记录ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            result = self.collection.delete_one({"_id": ObjectId(record_id)})
            return result.deleted_count > 0
            
        except Exception as e:
            logger.error(f"Failed to delete hotfix record {record_id}: {e}")
            raise
    
    def delete_expired_hotfix_records(self, expire_days: int = 60) -> int:
        """
        删除过期的Hotfix记录
        
        Args:
            expire_days: 过期天数，默认60天
            
        Returns:
            int: 删除的记录数量
        """
        try:
            # 计算过期时间点
            expire_time = timeMgr.getCurrentDateTime() - timedelta(days=expire_days)
            
            # 删除created_at小于过期时间的记录
            result = self.collection.delete_many({"created_at": {"$lt": expire_time}})
            
            deleted_count = result.deleted_count
            logger.info(f"Deleted {deleted_count} expired hotfix records (older than {expire_days} days)")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete expired hotfix records: {e}")
            raise
    
    def get_user_statistics(self, username: str = None) -> Dict:
        """
        获取用户统计信息
        
        Args:
            username: 用户名，如果为None则获取所有用户统计
            
        Returns:
            Dict: 统计信息
        """
        try:
            pipeline = []
            
            # 用户过滤
            if username:
                pipeline.append({"$match": {"username": username}})
            
            # 聚合统计
            pipeline.extend([
                {
                    "$group": {
                        "_id": "$username",
                        "total_records": {"$sum": 1},
                        "latest_record": {"$max": "$created_at"},
                        "earliest_record": {"$min": "$created_at"}
                    }
                },
                {
                    "$sort": {"total_records": -1}
                }
            ])
            
            results = list(self.collection.aggregate(pipeline))
            
            # 转换datetime为ISO格式
            for result in results:
                if "latest_record" in result:
                    result["latest_record"] = result["latest_record"].isoformat()
                if "earliest_record" in result:
                    result["earliest_record"] = result["earliest_record"].isoformat()
            
            return {
                "user_statistics": results,
                "total_users": len(results)
            }
            
        except Exception as e:
            logger.error(f"Failed to get user statistics: {e}")
            raise

# 全局实例
hotfix_mongo = None

def get_hotfix_mongo() -> HotfixMongoImp:
    """获取HotfixMongoImp实例（单例模式）"""
    global hotfix_mongo
    if hotfix_mongo is None:
        hotfix_mongo = HotfixMongoImp()
    return hotfix_mongo

# region end

# region hotfixWatcherMongoImp

class HotfixWatcherMongoImp(MongoImp):
    """
    Hotfix 目录定时监控的 MongoDB 存储类
    
    Collection:
      - hotfix_watch_state       : 各 side 的最新 changelist 版本记录
      - hotfix_conflict_notified : 已通知过的冲突去重记录
    """

    STATE_COLLECTION = "hotfix_watch_state"
    NOTIFIED_COLLECTION = "hotfix_conflict_notified"

    def __init__(self, connection_string: str = None, database_name: str = "work_flow"):
        super().__init__(connection_string, database_name)
        self.state_col = self.get_collection(self.STATE_COLLECTION)
        self.notified_col = self.get_collection(self.NOTIFIED_COLLECTION)
        self._ensure_indexes()

    def _ensure_indexes(self):
        """建立索引"""
        try:
            # state 按 watch_key ("side/branch_type") 唯一
            self.state_col.create_index([("watch_key", ASCENDING)], unique=True)
            # notified 按 conflict_key 唯一
            self.notified_col.create_index([("conflict_key", ASCENDING)], unique=True)
        except Exception as e:
            logger.warning(f"HotfixWatcherMongoImp: create index failed: {e}")

    # ── 版本状态 ──────────────────────────────────────────

    def load_state(self) -> dict:
        """
        读取所有监控项的版本状态

        Returns: {"side/branch_type": changelist_number}
        """
        try:
            docs = list(self.state_col.find({}, {"_id": 0, "watch_key": 1, "changelist": 1}))
            return {d["watch_key"]: d["changelist"] for d in docs}
        except Exception as e:
            logger.warning(f"HotfixWatcherMongoImp: load_state failed: {e}")
            return {}

    def save_state(self, changelists: dict):
        """
        保存各监控项的版本状态（upsert）

        Args:
            changelists: {"side/branch_type": changelist_number}
        """
        now = datetime.now(timezone.utc)
        for watch_key, cl in changelists.items():
            try:
                self.state_col.update_one(
                    {"watch_key": watch_key},
                    {"$set": {"changelist": cl, "updated_at": now}},
                    upsert=True
                )
            except Exception as e:
                logger.warning(f"HotfixWatcherMongoImp: save_state watch_key={watch_key} failed: {e}")

    def get_state_updated_at(self) -> Optional[str]:
        """返回最近一次 state 更新时间（ISO 字符串）"""
        try:
            doc = self.state_col.find_one({}, sort=[("updated_at", DESCENDING)])
            if doc and doc.get("updated_at"):
                return doc["updated_at"].isoformat()
        except Exception as e:
            logger.warning(f"HotfixWatcherMongoImp: get_state_updated_at failed: {e}")
        return None

    # ── 已通知冲突 ────────────────────────────────────────

    def load_notified_conflicts(self) -> dict:
        """
        读取所有已通知的冲突记录
        
        Returns: {conflict_key: {...}}
        """
        try:
            docs = list(self.notified_col.find({}, {"_id": 0}))
            return {d["conflict_key"]: d for d in docs}
        except Exception as e:
            logger.warning(f"HotfixWatcherMongoImp: load_notified_conflicts failed: {e}")
            return {}

    def upsert_notified_conflict(self, conflict_key: str, record: dict):
        """
        写入或更新一条已通知冲突记录
        
        Args:
            conflict_key: 冲突唯一标识
            record: 冲突详情 dict
        """
        try:
            doc = dict(record)
            doc["conflict_key"] = conflict_key
            self.notified_col.update_one(
                {"conflict_key": conflict_key},
                {"$set": doc},
                upsert=True
            )
        except Exception as e:
            logger.warning(f"HotfixWatcherMongoImp: upsert_notified_conflict key={conflict_key} failed: {e}")

    def delete_notified_conflicts(self, conflict_keys: list):
        """
        删除一批已不存在的冲突记录
        
        Args:
            conflict_keys: 要删除的 conflict_key 列表
        """
        if not conflict_keys:
            return
        try:
            result = self.notified_col.delete_many({"conflict_key": {"$in": conflict_keys}})
            logger.info(f"HotfixWatcherMongoImp: deleted {result.deleted_count} stale conflict records")
        except Exception as e:
            logger.warning(f"HotfixWatcherMongoImp: delete_notified_conflicts failed: {e}")

    def count_notified_conflicts(self) -> int:
        """返回已通知冲突总数"""
        try:
            return self.notified_col.count_documents({})
        except Exception as e:
            logger.warning(f"HotfixWatcherMongoImp: count failed: {e}")
            return 0


# 全局单例
hotfix_watcher_mongo = None


def get_hotfix_watcher_mongo() -> HotfixWatcherMongoImp:
    """获取 HotfixWatcherMongoImp 实例（单例模式）"""
    global hotfix_watcher_mongo
    if hotfix_watcher_mongo is None:
        hotfix_watcher_mongo = HotfixWatcherMongoImp()
    return hotfix_watcher_mongo

# region end

# region excelIdMongoImp

class ExcelIdMongoImp(MongoImp):
    """Excel ID相关的MongoDB操作类"""
    
    COLLECTION_NAME = "excel_ids"
    
    def __init__(self, connection_string: str = None, database_name: str = "work_flow"):
        super().__init__(connection_string, database_name)
        self.collection = self.get_collection(self.COLLECTION_NAME)
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """创建索引"""
        try:
            # 核心查询路径（唯一索引）
            self.collection.create_index([
                ("excelName", ASCENDING),
                ("sheetName", ASCENDING),
                ("id", ASCENDING)
            ], unique=True)
            logger.info(f"Successfully created indexes for {self.COLLECTION_NAME}")
        except Exception as e:
            logger.error(f"Failed to create indexes for {self.COLLECTION_NAME}: {e}")
    
    def bulk_save_ids(self, records: List[Dict]):
        """批量保存ID记录"""
        if not records:
            return
            
        from pymongo import UpdateOne
        operations = []
        now = datetime.now()
        
        for record in records:
            # 确保有 createdAt 和 updatedAt
            record.setdefault('createdAt', now)
            record['updatedAt'] = now
            
            filter_query = {
                "excelName": record["excelName"],
                "sheetName": record["sheetName"],
                "id": record["id"]
            }
            
            # 使用 $set 进行 upsert，保留原始 createdAt 如果记录已存在
            update_query = {
                "$set": record,
                "$setOnInsert": {"createdAt": now}
            }
            # 移除 $set 中的 createdAt，因为它由 $setOnInsert 处理
            if "createdAt" in record:
                del record["createdAt"]
                
            operations.append(UpdateOne(filter_query, update_query, upsert=True))
            
        if operations:
            try:
                result = self.collection.bulk_write(operations, ordered=False)
                logger.info(f"Bulk saved {len(records)} IDs: {result.upserted_count} upserted, {result.modified_count} modified")
                return result
            except Exception as e:
                logger.error(f"Failed to bulk save IDs: {e}")
                raise

    def get_id_info(self, excel_name: str, sheet_name: str, id_val: str) -> Optional[Dict]:
        """查询某个ID的信息"""
        try:
            return self.collection.find_one({
                "excelName": excel_name,
                "sheetName": sheet_name,
                "id": id_val
            }, {"_id": 0})
        except Exception as e:
            logger.error(f"Failed to get ID info: {e}")
            raise
    
    def allow_id(self, excel_name: str, sheet_name: str, id_val: str) -> bool:
        """设置 allow_until 为当前时间 10 分钟后"""
        try:
            allow_until = datetime.now() + timedelta(minutes=10)
            result = self.collection.update_one(
                {"excelName": excel_name, "sheetName": sheet_name, "id": id_val},
                {"$set": {"allow_until": allow_until}}
            )
            return result.matched_count > 0
        except Exception as e:
            logger.error(f"Failed to allow ID: {e}")
            raise

    def add_id(self, record: Dict) -> bool:
        """增加或更新单个ID"""
        try:
            now = datetime.now()
            record.setdefault('createdAt', now)
            record['updatedAt'] = now
            
            filter_query = {
                "excelName": record["excelName"],
                "sheetName": record["sheetName"],
                "id": record["id"]
            }
            
            update_query = {
                "$set": record,
                "$setOnInsert": {"createdAt": now}
            }
            if "createdAt" in record:
                del record["createdAt"]
                
            self.collection.update_one(filter_query, update_query, upsert=True)
            return True
        except Exception as e:
            logger.error(f"Failed to add ID: {e}")
            raise

    def update_id(self, excel_name: str, sheet_name: str, id_val: str, update_fields: Dict) -> bool:
        """更新 ID 的特定字段"""
        try:
            now = datetime.now()
            update_fields['updatedAt'] = now
            
            result = self.collection.update_one(
                {
                    "excelName": excel_name,
                    "sheetName": sheet_name,
                    "id": id_val
                },
                {"$set": update_fields}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update ID: {e}")
            raise

    def delete_id(self, excel_name: str, sheet_name: str, id_val: str) -> bool:
        """删除某个ID"""
        try:
            result = self.collection.delete_one({
                "excelName": excel_name,
                "sheetName": sheet_name,
                "id": id_val
            })
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete ID: {e}")
            raise

    def delete_all_ids(self) -> int:
        """删除所有 ID"""
        try:
            result = self.collection.delete_many({})
            logger.info(f"Successfully deleted all {result.deleted_count} IDs from {self.COLLECTION_NAME}")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Failed to delete all IDs: {e}")
            raise

    def list_ids(self, query: Dict = None, limit: int = 100, skip: int = 0) -> List[Dict]:
        """列表查询 ID"""
        try:
            query = query or {}
            match_mode = str(query.get("matchMode") or "").strip().lower()
            exact = bool(query.get("exact")) or match_mode == "exact"

            mongo_query = {}
            excel_name = query.get("excelName")
            sheet_name = query.get("sheetName")
            id_val = query.get("id")

            if exact:
                if excel_name:
                    mongo_query["excelName"] = str(excel_name)
                if sheet_name:
                    mongo_query["sheetName"] = str(sheet_name)
                if id_val:
                    mongo_query["id"] = str(id_val)
            else:
                if excel_name:
                    mongo_query["excelName"] = {"$regex": re.escape(str(excel_name)), "$options": "i"}
                if sheet_name:
                    mongo_query["sheetName"] = {"$regex": re.escape(str(sheet_name)), "$options": "i"}
                if id_val:
                    mongo_query["id"] = {"$regex": re.escape(str(id_val)), "$options": "i"}

            cursor = self.collection.find(mongo_query, {"_id": 0}).skip(skip).limit(limit)

            if exact and excel_name and sheet_name:
                cursor = cursor.hint([("excelName", 1), ("sheetName", 1), ("id", 1)]).sort([("id", 1)])
            else:
                cursor = cursor.sort([("excelName", 1), ("sheetName", 1), ("id", 1)])

            return list(cursor)
        except Exception as e:
            logger.error(f"Failed to list IDs: {e}")
            raise

    def count_ids(self, query: Dict = None) -> int:
        """查询符合条件的 ID 总数"""
        try:
            query = query or {}
            match_mode = str(query.get("matchMode") or "").strip().lower()
            exact = bool(query.get("exact")) or match_mode == "exact"

            mongo_query = {}
            excel_name = query.get("excelName")
            sheet_name = query.get("sheetName")
            id_val = query.get("id")

            if exact:
                if excel_name:
                    mongo_query["excelName"] = str(excel_name)
                if sheet_name:
                    mongo_query["sheetName"] = str(sheet_name)
                if id_val:
                    mongo_query["id"] = str(id_val)
            else:
                if excel_name:
                    mongo_query["excelName"] = {"$regex": re.escape(str(excel_name)), "$options": "i"}
                if sheet_name:
                    mongo_query["sheetName"] = {"$regex": re.escape(str(sheet_name)), "$options": "i"}
                if id_val:
                    mongo_query["id"] = {"$regex": re.escape(str(id_val)), "$options": "i"}

            if exact and excel_name and sheet_name:
                return self.collection.count_documents(
                    mongo_query,
                    hint=[("excelName", 1), ("sheetName", 1), ("id", 1)]
                )

            return self.collection.count_documents(mongo_query)
        except Exception as e:
            logger.error(f"Failed to count IDs: {e}")
            raise

    def list_excels(self) -> List[str]:
        """列出所有唯一的 Excel 名称"""
        try:
            return self.collection.distinct("excelName")
        except Exception as e:
            logger.error(f"Failed to list excels: {e}")
            raise

    def list_sheets(self, excel_name: str) -> List[str]:
        """列出指定 Excel 下的所有唯一 Sheet 名称"""
        try:
            return self.collection.distinct("sheetName", {"excelName": excel_name})
        except Exception as e:
            logger.error(f"Failed to list sheets for {excel_name}: {e}")
            raise


# 全局实例
excel_id_mongo = None

def get_excel_id_mongo() -> ExcelIdMongoImp:
    """获取ExcelIdMongoImp实例（单例模式）"""
    global excel_id_mongo
    if excel_id_mongo is None:
        excel_id_mongo = ExcelIdMongoImp()
    return excel_id_mongo

# region end

# region excelIdHistoryMongoImp

class ExcelIdHistoryMongoImp(MongoImp):
    COLLECTION_NAME = "excel_id_history"

    def __init__(self, connection_string: str = None, database_name: str = "work_flow"):
        super().__init__(connection_string, database_name)
        self.collection = self.get_collection(self.COLLECTION_NAME)
        self._ensure_indexes()

    def _ensure_indexes(self):
        try:
            self.collection.create_index([("timestamp", DESCENDING)])
            self.collection.create_index([
                ("excelName", ASCENDING),
                ("sheetName", ASCENDING),
                ("id", ASCENDING),
                ("timestamp", DESCENDING)
            ])
            self.collection.create_index([("action", ASCENDING), ("timestamp", DESCENDING)])
            self.collection.create_index([("operator", ASCENDING), ("timestamp", DESCENDING)])
            logger.info(f"Successfully created indexes for {self.COLLECTION_NAME}")
        except Exception as e:
            logger.error(f"Failed to create indexes for {self.COLLECTION_NAME}: {e}")

    def add_history(self, record: Dict) -> bool:
        try:
            record.setdefault("timestamp", datetime.now())
            self.collection.insert_one(record)
            return True
        except Exception as e:
            logger.error(f"Failed to add id history: {e}")
            raise

    def list_history(self, query: Dict = None, limit: int = 100, skip: int = 0) -> List[Dict]:
        try:
            mongo_query = {}
            if query:
                if query.get("excelName"):
                    mongo_query["excelName"] = {"$regex": query["excelName"], "$options": "i"}
                if query.get("sheetName"):
                    mongo_query["sheetName"] = {"$regex": query["sheetName"], "$options": "i"}
                if query.get("id"):
                    mongo_query["id"] = {"$regex": query["id"], "$options": "i"}
                if query.get("action"):
                    mongo_query["action"] = str(query["action"]).strip()
                if query.get("operator"):
                    mongo_query["operator"] = {"$regex": query["operator"], "$options": "i"}
                if "success" in query and query["success"] is not None and query["success"] != "":
                    mongo_query["success"] = bool(query["success"])

            cursor = self.collection.find(mongo_query, {"_id": 0}).skip(skip).limit(limit).sort([("timestamp", -1)])
            return list(cursor)
        except Exception as e:
            logger.error(f"Failed to list id history: {e}")
            raise

    def count_history(self, query: Dict = None) -> int:
        try:
            mongo_query = {}
            if query:
                if query.get("excelName"):
                    mongo_query["excelName"] = {"$regex": query["excelName"], "$options": "i"}
                if query.get("sheetName"):
                    mongo_query["sheetName"] = {"$regex": query["sheetName"], "$options": "i"}
                if query.get("id"):
                    mongo_query["id"] = {"$regex": query["id"], "$options": "i"}
                if query.get("action"):
                    mongo_query["action"] = str(query["action"]).strip()
                if query.get("operator"):
                    mongo_query["operator"] = {"$regex": query["operator"], "$options": "i"}
                if "success" in query and query["success"] is not None and query["success"] != "":
                    mongo_query["success"] = bool(query["success"])
            return self.collection.count_documents(mongo_query)
        except Exception as e:
            logger.error(f"Failed to count id history: {e}")
            raise


excel_id_history_mongo = None

def get_excel_id_history_mongo() -> ExcelIdHistoryMongoImp:
    global excel_id_history_mongo
    if excel_id_history_mongo is None:
        excel_id_history_mongo = ExcelIdHistoryMongoImp()
    return excel_id_history_mongo

# region end

# region mailMongoImp

class MailMongoImp(MongoImp):
    """邮件工具相关的MongoDB操作类"""

    META_COLLECTION_NAME = 'mail_meta'
    RECORD_COLLECTION_NAME = 'mail_records'

    def __init__(self, connection_string: str = None, database_name: str = None):
        super().__init__(connection_string, database_name)
        self.meta_collection = self.get_collection(self.META_COLLECTION_NAME)
        self.record_collection = self.get_collection(self.RECORD_COLLECTION_NAME)

    @staticmethod
    def _normalize_mail_ids(values):
        if not isinstance(values, list):
            return []
        result = []
        for value in values:
            try:
                as_int = int(value)
            except (TypeError, ValueError):
                continue
            if as_int > 0:
                result.append(as_int)
        return result

    def load_mail_meta(self):
        doc = self.meta_collection.find_one({'meta_key': 'mail_meta'})
        if not isinstance(doc, dict):
            return None

        next_mail_id = doc.get('next_mail_id', 1)
        try:
            next_mail_id = int(next_mail_id)
        except (TypeError, ValueError):
            next_mail_id = 1
        if next_mail_id < 1:
            next_mail_id = 1

        return {
            'next_mail_id': next_mail_id,
            'mail_ids': self._normalize_mail_ids(doc.get('mail_ids', []))
        }

    def save_mail_meta(self, meta):
        if not isinstance(meta, dict):
            return False

        next_mail_id = meta.get('next_mail_id', 1)
        try:
            next_mail_id = int(next_mail_id)
        except (TypeError, ValueError):
            next_mail_id = 1
        if next_mail_id < 1:
            next_mail_id = 1

        mail_ids = self._normalize_mail_ids(meta.get('mail_ids', []))
        now = datetime.utcnow()

        self.meta_collection.update_one(
            {'meta_key': 'mail_meta'},
            {
                '$set': {
                    'next_mail_id': next_mail_id,
                    'mail_ids': mail_ids,
                    'updated_at': now
                },
                '$setOnInsert': {
                    'meta_key': 'mail_meta',
                    'created_at': now
                }
            },
            upsert=True
        )
        return True

    def load_mail_templates(self):
        doc = self.meta_collection.find_one({'meta_key': 'mail_templates'})
        if not isinstance(doc, dict):
            return []

        templates = doc.get('templates', [])
        if not isinstance(templates, list):
            return []

        result = []
        for item in templates:
            if isinstance(item, dict):
                result.append(item)
        return result

    def save_mail_templates(self, templates):
        if not isinstance(templates, list):
            return False

        normalized_templates = []
        for item in templates:
            if isinstance(item, dict):
                normalized_templates.append(item)

        now = datetime.utcnow()
        self.meta_collection.update_one(
            {'meta_key': 'mail_templates'},
            {
                '$set': {
                    'templates': normalized_templates,
                    'updated_at': now
                },
                '$setOnInsert': {
                    'meta_key': 'mail_templates',
                    'created_at': now
                }
            },
            upsert=True
        )
        return True

    def load_mail_record(self, mail_id):
        try:
            normalized_mail_id = int(mail_id)
        except (TypeError, ValueError):
            return None

        doc = self.record_collection.find_one({'mail_id': normalized_mail_id})
        if not isinstance(doc, dict):
            return None

        payload = doc.get('payload')
        return payload if isinstance(payload, dict) else None

    def save_mail_record(self, mail_record):
        if not isinstance(mail_record, dict):
            return False

        try:
            mail_id = int(mail_record.get('mailId', 0))
        except (TypeError, ValueError):
            return False
        if mail_id <= 0:
            return False

        now = datetime.utcnow()
        self.record_collection.update_one(
            {'mail_id': mail_id},
            {
                '$set': {
                    'status': str(mail_record.get('status', '')).strip() or 'pending_submit',
                    'creator': str(mail_record.get('creator', '')).strip(),
                    'update_time': str(mail_record.get('updateTime', '')).strip(),
                    'payload': mail_record,
                    'updated_at': now
                },
                '$setOnInsert': {
                    'mail_id': mail_id,
                    'created_at': now
                }
            },
            upsert=True
        )
        return True

    def delete_mail_record(self, mail_id):
        try:
            normalized_mail_id = int(mail_id)
        except (TypeError, ValueError):
            return False
        if normalized_mail_id <= 0:
            return False

        self.record_collection.delete_one({'mail_id': normalized_mail_id})
        return True

    def list_mail_ids(self):
        cursor = self.record_collection.find({}, {'mail_id': 1, '_id': 0}).sort('mail_id', DESCENDING)
        ids = []
        for doc in cursor:
            try:
                value = int(doc.get('mail_id', 0))
            except (TypeError, ValueError):
                continue
            if value > 0:
                ids.append(value)
        return sorted(set(ids), reverse=True)

    def list_mail_records(self, status='', server_env_type='', skip=0, limit=20, sort_by='mail_id', sort_order='desc'):
        query = {}

        status_values = []
        if isinstance(status, (list, tuple, set)):
            status_values = [str(item).strip() for item in status if str(item).strip()]
        else:
            raw_status = str(status or '').strip()
            if raw_status:
                status_values = [item.strip() for item in raw_status.split(',') if item.strip()]

        if len(status_values) == 1:
            query['status'] = status_values[0]
        elif len(status_values) > 1:
            query['status'] = {'$in': status_values}

        env_values = []
        if isinstance(server_env_type, (list, tuple, set)):
            env_values = [str(item).strip().lower() for item in server_env_type if str(item).strip()]
        else:
            raw_env = str(server_env_type or '').strip().lower()
            if raw_env:
                env_values = [item.strip() for item in raw_env.split(',') if item.strip()]

        if env_values:
            normalized_env_values = []
            for env in env_values:
                value = str(env or '').strip().lower()
                if value in ['online', 'debugging'] and value not in normalized_env_values:
                    normalized_env_values.append(value)

            env_match_conditions = []
            for env in normalized_env_values:
                env_match_conditions.append({'payload.serverEnvTypes': env})
                env_match_conditions.append({'payload.region': {'$regex': f'^{re.escape(env)}\\|'}})
                env_match_conditions.append({'payload.region': env})

            if env_match_conditions:
                query['$or'] = env_match_conditions

        try:
            normalized_skip = int(skip)
        except (TypeError, ValueError):
            normalized_skip = 0
        if normalized_skip < 0:
            normalized_skip = 0

        try:
            normalized_limit = int(limit)
        except (TypeError, ValueError):
            normalized_limit = 20
        if normalized_limit < 1:
            normalized_limit = 20

        normalized_sort_by = str(sort_by or 'mail_id').strip().lower()
        if normalized_sort_by in ['id', 'mailid']:
            normalized_sort_by = 'mail_id'
        if normalized_sort_by not in ['mail_id', 'create_time', 'update_time', 'status']:
            normalized_sort_by = 'mail_id'

        normalized_sort_order = str(sort_order or 'desc').strip().lower()
        sort_direction = DESCENDING
        if normalized_sort_order in ['asc', 'ascend', 'ascending', '1']:
            sort_direction = ASCENDING

        total = self.record_collection.count_documents(query)
        cursor = self.record_collection.find(
            query,
            {'payload': 1, '_id': 0}
        ).sort(normalized_sort_by, sort_direction).skip(normalized_skip).limit(normalized_limit)

        records = []
        for doc in cursor:
            payload = doc.get('payload')
            if isinstance(payload, dict):
                records.append(payload)

        return records, total


mail_mongo = None


def get_mail_mongo() -> MailMongoImp:
    """获取MailMongoImp实例（单例模式）"""
    global mail_mongo
    if mail_mongo is None:
        mail_mongo = MailMongoImp()
    return mail_mongo

# region end
