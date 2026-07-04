#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MongoDB集群初始化脚本
用于初始化work_flow数据库、hotfix_records集合、mail_records和相关索引
"""

import sys
import os
import logging
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, OperationFailure, CollectionInvalid

# 添加父目录到路径，以便导入config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('mongodb_init.log')
    ]
)
logger = logging.getLogger(__name__)


class MongoDBClusterInitializer:
    """MongoDB集群初始化器"""
    
    def __init__(self):
        """初始化连接配置"""
        self.host = config.mongo_host
        self.port = config.mongo_port
        self.database_name = config.mongo_db
        self.username = config.mongo_user
        self.password = config.mongo_password
        
        # 构建连接字符串
        self.connection_string = f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/"
        
        self.client = None
        self.db = None
        
        logger.info(f"初始化MongoDB连接配置: {self.host}:{self.port}/{self.database_name}")
    
    def connect(self):
        """连接到MongoDB"""
        try:
            self.client = MongoClient(
                self.connection_string,
                serverSelectionTimeoutMS=5000,  # 5秒超时
                connectTimeoutMS=5000,
                socketTimeoutMS=5000
            )
            
            # 测试连接
            self.client.admin.command('ping')
            logger.info("MongoDB连接成功")
            
            # 获取MongoDB版本信息
            try:
                server_info = self.client.server_info()
                version = server_info.get('version', 'unknown')
                logger.info(f"MongoDB服务器版本: {version}")
            except Exception as e:
                logger.warning(f"无法获取MongoDB版本信息: {e}")
            
            # 获取数据库引用
            self.db = self.client[self.database_name]
            return True
            
        except ConnectionFailure as e:
            logger.error(f"MongoDB连接失败: {e}")
            logger.error(f"请检查MongoDB服务是否运行，以及连接配置是否正确")
            logger.error(f"连接字符串: {self.connection_string}")
            return False
        except Exception as e:
            logger.error(f"连接过程中发生错误: {e}")
            return False
    
    def create_database_and_collection(self):
        """创建数据库和集合"""
        try:
            # 检查数据库是否存在
            db_list = self.client.list_database_names()
            if self.database_name in db_list:
                logger.info(f"数据库 '{self.database_name}' 已存在")
            else:
                logger.info(f"创建数据库 '{self.database_name}'")
            
            # 检查集合是否存在
            collection_list = self.db.list_collection_names()
            collection_names = [
                'hotfix_records',
                'mail_meta',
                'mail_records'
            ]

            for collection_name in collection_names:
                if collection_name in collection_list:
                    logger.info(f"集合 '{collection_name}' 已存在")
                else:
                    self.db.create_collection(collection_name)
                    logger.info(f"成功创建集合 '{collection_name}'")
            
            return True
            
        except CollectionInvalid as e:
            logger.error(f"集合创建失败: {e}")
            return False
        except Exception as e:
            logger.error(f"创建数据库和集合时发生错误: {e}")
            return False
    
    def create_indexes(self):
        """创建索引"""
        try:
            indexes_by_collection = {
                'hotfix_records': [
                    {
                        'keys': [('username', ASCENDING)],
                        'name': 'idx_username',
                        'background': True
                    },
                    {
                        'keys': [('timestamp', DESCENDING)],
                        'name': 'idx_timestamp_desc',
                        'background': True
                    },
                    {
                        'keys': [('file_pairs.old_file', ASCENDING)],
                        'name': 'idx_old_file',
                        'background': True
                    },
                    {
                        'keys': [('file_pairs.new_file', ASCENDING)],
                        'name': 'idx_new_file',
                        'background': True
                    },
                    {
                        'keys': [('_id', ASCENDING), ('timestamp', ASCENDING)],
                        'name': 'idx_shard_key',
                        'background': True
                    },
                    {
                        'keys': [('hotfixContent', 'text')],
                        'name': 'idx_hotfix_content_text',
                        'background': True,
                        'default_language': 'none'
                    },
                    {
                        'keys': [('tags', ASCENDING)],
                        'name': 'idx_tags',
                        'background': True
                    }
                ],
                'mail_meta': [
                    {
                        'keys': [('meta_key', ASCENDING)],
                        'name': 'meta_key_1',
                        'unique': True,
                        'background': True
                    }
                ],
                'mail_records': [
                    {
                        'keys': [('mail_id', ASCENDING)],
                        'name': 'mail_id_1',
                        'unique': True,
                        'background': True
                    },
                    {
                        'keys': [('status', ASCENDING)],
                        'name': 'status_1',
                        'background': True
                    },
                    {
                        'keys': [('update_time', DESCENDING)],
                        'name': 'update_time_-1',
                        'background': True
                    }
                ]
            }

            total_created_count = 0
            for collection_name, indexes_config in indexes_by_collection.items():
                collection = self.db[collection_name]
                existing_indexes = list(collection.list_indexes())
                existing_index_names = {idx['name'] for idx in existing_indexes}
                logger.info(f"集合 '{collection_name}' 现有索引: {existing_index_names}")

                for index_config in indexes_config:
                    index_name = index_config['name']
                    if index_name in existing_index_names:
                        logger.info(f"集合 '{collection_name}' 索引 '{index_name}' 已存在，跳过创建")
                        continue

                    try:
                        keys = index_config['keys']
                        index_options = {k: v for k, v in index_config.items() if k != 'keys'}
                        collection.create_index(keys, **index_options)
                        logger.info(f"集合 '{collection_name}' 成功创建索引: {index_name}")
                        total_created_count += 1
                    except Exception as e:
                        logger.error(f"集合 '{collection_name}' 创建索引 '{index_name}' 失败: {e}")

            logger.info(f"索引创建完成，新创建 {total_created_count} 个索引")
            return True
            
        except Exception as e:
            logger.error(f"创建索引时发生错误: {e}")
            return False
    
    def setup_sharding(self):
        """配置分片 (可选，需要分片集群环境)"""
        try:
            # 检查是否为分片集群
            is_sharded = False
            try:
                shard_status = self.client.admin.command("listShards")
                is_sharded = True
                logger.info("检测到分片集群环境")
            except OperationFailure:
                logger.info("非分片集群环境，跳过分片配置")
                return True
            
            if not is_sharded:
                return True
            
            # 启用数据库分片
            try:
                self.client.admin.command("enableSharding", self.database_name)
                logger.info(f"为数据库 '{self.database_name}' 启用分片")
            except OperationFailure as e:
                if "already enabled" in str(e):
                    logger.info(f"数据库 '{self.database_name}' 分片已启用")
                else:
                    raise
            
            # 配置集合分片
            collection_full_name = f"{self.database_name}.hotfix_records"
            # MongoDB分片键限制：不能同时使用升序和降序字段
            # 使用_id和timestamp都为升序，或者使用哈希分片
            shard_key_options = [
                {"_id": 1, "timestamp": 1},  # 选项1：都使用升序
                {"_id": "hashed"},           # 选项2：使用哈希分片
                {"timestamp": 1}             # 选项3：仅使用timestamp
            ]
            
            shard_success = False
            for i, shard_key in enumerate(shard_key_options):
                try:
                    self.client.admin.command(
                        "shardCollection",
                        collection_full_name,
                        key=shard_key
                    )
                    logger.info(f"为集合 '{collection_full_name}' 配置分片成功，分片键: {shard_key}")
                    shard_success = True
                    break
                except OperationFailure as e:
                    if "already sharded" in str(e):
                        logger.info(f"集合 '{collection_full_name}' 已配置分片")
                        shard_success = True
                        break
                    else:
                        logger.warning(f"分片配置选项 {i+1} 失败 (分片键: {shard_key}): {e}")
                        if i == len(shard_key_options) - 1:  # 最后一个选项也失败了
                            logger.error(f"所有分片配置选项都失败，最后错误: {e}")
            
            if not shard_success:
                logger.warning("分片配置失败，但继续执行其他初始化步骤")
            
            return True
            
        except Exception as e:
            logger.error(f"配置分片时发生错误: {e}")
            return False
    
    def verify_setup(self):
        """验证初始化结果"""
        try:
            # 验证数据库
            db_list = self.client.list_database_names()
            if self.database_name not in db_list:
                logger.error(f"数据库 '{self.database_name}' 不存在")
                return False
            
            # 验证集合
            collection_list = self.db.list_collection_names()
            if "hotfix_records" not in collection_list:
                logger.error("集合 'hotfix_records' 不存在")
                return False
            
            # 验证索引
            collection = self.db.hotfix_records
            indexes = list(collection.list_indexes())
            index_names = [idx['name'] for idx in indexes]
            
            logger.info(f"集合索引: {index_names}")
            
            # 检查是否为分片集合
            is_sharded_collection = False
            try:
                shard_info = self.client.admin.command("listShards")
                # 检查集合是否已分片
                config_db = self.client.config
                collections_info = config_db.collections.find_one({
                    "_id": f"{self.database_name}.hotfix_records"
                })
                if collections_info:
                    is_sharded_collection = True
                    logger.info("检测到分片集合环境")
                    logger.info(f"分片键: {collections_info.get('key', 'unknown')}")
            except Exception:
                logger.info("非分片集合环境")
            
            # 插入测试文档
            test_timestamp = datetime.utcnow()
            test_doc = {
                "username": "test_user",
                "timestamp": test_timestamp,
                "file_pairs": [
                    {"old_file": "test_old.lua", "new_file": "test_new.lua"}
                ],
                "hotfixContent": "test hotfix content",
                "_test": True
            }
            
            try:
                result = collection.insert_one(test_doc)
                test_doc_id = result.inserted_id
                logger.info(f"测试文档插入成功，ID: {test_doc_id}")
                
                # 删除测试文档 - 使用_id进行精确匹配（符合分片集合要求）
                if is_sharded_collection:
                    # 对于分片集合，使用_id进行删除
                    delete_result = collection.delete_one({"_id": test_doc_id})
                else:
                    # 对于非分片集合，可以使用任意条件
                    delete_result = collection.delete_one({"_id": test_doc_id})
                
                if delete_result.deleted_count > 0:
                    logger.info("测试文档已删除")
                else:
                    logger.warning("测试文档删除失败")
                    
            except Exception as e:
                logger.error(f"测试文档操作失败: {e}")
                # 尝试清理可能残留的测试文档
                try:
                    collection.delete_many({"_test": True, "username": "test_user"})
                except Exception:
                    pass  # 忽略清理错误
                return False
            
            logger.info("MongoDB集群初始化验证成功")
            return True
            
        except Exception as e:
            logger.error(f"验证过程中发生错误: {e}")
            return False
    
    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()
            logger.info("MongoDB连接已关闭")
    
    def run(self):
        """执行完整的初始化流程"""
        logger.info("开始MongoDB集群初始化...")
        
        try:
            # 1. 连接数据库
            if not self.connect():
                return False
            
            # 2. 创建数据库和集合
            if not self.create_database_and_collection():
                return False
            
            # 3. 创建索引
            if not self.create_indexes():
                return False
            
            # 4. 配置分片 (可选)
            if not self.setup_sharding():
                return False
            
            # 5. 验证设置
            if not self.verify_setup():
                return False
            
            logger.info("MongoDB集群初始化完成!")
            return True
            
        except Exception as e:
            logger.error(f"初始化过程中发生未预期的错误: {e}")
            return False
        finally:
            self.close()


def main():
    """主函数"""
    print("MongoDB集群初始化脚本")
    print("=" * 50)
    
    initializer = MongoDBClusterInitializer()
    success = initializer.run()
    
    if success:
        print("\n✅ MongoDB集群初始化成功!")
        sys.exit(0)
    else:
        print("\n❌ MongoDB集群初始化失败!")
        sys.exit(1)


if __name__ == "__main__":
    main()