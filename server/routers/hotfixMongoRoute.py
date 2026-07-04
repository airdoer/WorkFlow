#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from flask import request, jsonify
from typing import Dict, Any

from utility import const
import g
from dbImp.mongoImp import get_hotfix_mongo

logger = logging.getLogger(__name__)


@g.app.route('/api/hotfix/save', methods=['POST'])
def save_hotfix_record():
    """
    保存Hotfix记录
    
    请求体格式:
    {
        "username": "用户名",
        "file_pairs": [
            {
                "raw_file_name": "原始文件路径",
                "old_file": "旧文件路径",
                "new_file": "新文件路径",
                "old_file_content": "旧文件内容(可选)",
                "new_file_content": "新文件内容(可选)"
            }
        ],
        "hotfix_content": "Hotfix内容",
        "additional_info": {}  // 可选的额外信息
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "code": -1,
                "message": "请求体不能为空"
            }), 400
        
        # 验证必需字段
        username = data.get('username')
        file_pairs = data.get('file_pairs', [])
        hotfix_content = data.get('hotfix_content', '')
        additional_info = data.get('additional_info', {})
        tags = data.get('tags', [])
        
        if not username:
            return jsonify({
                "code": -1,
                "message": "用户名不能为空"
            }), 400
        
        if not file_pairs:
            return jsonify({
                "code": -1,
                "message": "文件对列表不能为空"
            }), 400
        
        if not hotfix_content:
            return jsonify({
                "code": -1,
                "message": "Hotfix内容不能为空"
            }), 400
        
        # 验证文件对格式
        for i, pair in enumerate(file_pairs):
            if not isinstance(pair, dict):
                return jsonify({
                    "code": -1,
                    "message": f"文件对 {i} 格式错误"
                }), 400
            
            if 'raw_file_name' not in pair:
                return jsonify({
                    "code": -1,
                    "message": f"文件对 {i} 缺少必需字段 raw_file_name"
                }), 400

            if 'old_file' not in pair or 'new_file' not in pair:
                return jsonify({
                    "code": -1,
                    "message": f"文件对 {i} 缺少必需字段 old_file 或 new_file"
                }), 400
            raw_file_name = pair['raw_file_name']
            if not isinstance(raw_file_name, str):
                return jsonify({
                    "code": -1,
                    "message": f"文件对 {i} 的 raw_file_name 必须是字符串类型"
                }), 400
            # 验证文件内容字段（可选）
            if 'old_file_content' in pair and not isinstance(pair['old_file_content'], str):
                return jsonify({
                    "code": -1,
                    "message": f"文件对 {i} 的 old_file_content 必须是字符串类型"
                }), 400
            
            if 'new_file_content' in pair and not isinstance(pair['new_file_content'], str):
                return jsonify({
                    "code": -1,
                    "message": f"文件对 {i} 的 new_file_content 必须是字符串类型"
                }), 400
        
        # 保存记录
        hotfix_mongo = get_hotfix_mongo()
        record_id = hotfix_mongo.save_hotfix_record(
            username=username,
            file_pairs=file_pairs,
            hotfix_content=hotfix_content,
            tags=tags,
            additional_info=additional_info
        )
        
        logger.info(f"Hotfix record saved successfully: {record_id}")
        
        return jsonify({
            "code": 0,
            "message": "Hotfix记录保存成功",
            "data": {
                "record_id": record_id
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to save hotfix record: {e}")
        return jsonify({
            "code": -1,
            "message": f"保存失败: {str(e)}"
        }), 500


@g.app.route('/api/hotfix/query', methods=['GET'])
def query_hotfix_records():
    """
    查询Hotfix记录
    
    查询参数:
    - username: 用户名过滤
    - start_time: 开始时间 (ISO格式: 2024-01-01T00:00:00Z)
    - end_time: 结束时间 (ISO格式: 2024-01-01T23:59:59Z)
    - file_name: 文件名过滤（模糊匹配）
    - limit: 返回记录数限制 (默认100)
    - skip: 跳过记录数 (默认0)
    """
    try:
        # 获取查询参数
        username = request.args.get('username')
        start_time_str = request.args.get('start_time')
        end_time_str = request.args.get('end_time')
        file_name = request.args.get('file_name')
        remark = request.args.get('remark')
        record_id = request.args.get('record_id')
        tags_str = request.args.get('tags')
        tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else None
        limit = int(request.args.get('limit', 100))
        skip = int(request.args.get('skip', 0))
        
        # 转换时间格式
        start_time = None
        end_time = None
        
        if start_time_str:
            try:
                startTime_datetime = datetime.strptime(start_time_str, const.TIME_FORMAT)
                start_time = startTime_datetime
            except ValueError:
                logger.error(f"start_time格式错误: {start_time_str}")
                return jsonify({
                    "code": -1,
                    "message": "start_time格式错误，请使用指定格式: 2024-01-01 00:00:00"
                }), 400
        
        if end_time_str:
            try:
                endTime_datetime = datetime.strptime(end_time_str, const.TIME_FORMAT)
                end_time = endTime_datetime
            except ValueError:
                logger.error(f"end_time格式错误: {end_time_str}")
                return jsonify({
                    "code": -1,
                    "message": "end_time格式错误，请使用指定格式: 2024-01-01 23:59:59"
                }), 400
        
        # 验证limit和skip
        if limit <= 0 or limit > 1000:
            logger.error(f"limit格式错误: {limit}")
            return jsonify({
                "code": -1,
                "message": "limit必须在1-1000之间"
            }), 400
        
        if skip < 0:
            logger.error(f"skip格式错误: {skip}")
            return jsonify({
                "code": -1,
                "message": "skip不能为负数"
            }), 400
        
        # 查询记录
        hotfix_mongo = get_hotfix_mongo()
        records, total_count = hotfix_mongo.find_hotfix_records(
            username=username,
            start_time=start_time,
            end_time=end_time,
            file_name=file_name,
            remark=remark,
            record_id=record_id,
            tags=tags,
            limit=limit,
            skip=skip
        )
        
        logger.info(f"Query hotfix records: found {len(records)} records, total {total_count}")
        
        return jsonify({
            "code": 0,
            "message": "查询成功",
            "data": {
                "records": records,
                "total": total_count,
                "limit": limit,
                "skip": skip
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to query hotfix records: {e}")
        return jsonify({
            "code": -1,
            "message": f"查询失败: {str(e)}"
        }), 500


@g.app.route('/api/hotfix/detail/<record_id>', methods=['GET'])
def get_hotfix_record_detail(record_id: str):
    """
    获取Hotfix记录详情
    
    路径参数:
    - record_id: 记录ID
    """
    try:
        if not record_id:
            return jsonify({
                "code": -1,
                "message": "记录ID不能为空"
            }), 400
        
        # 获取记录详情
        hotfix_mongo = get_hotfix_mongo()
        record = hotfix_mongo.get_hotfix_record_by_id(record_id)
        
        if not record:
            return jsonify({
                "code": -1,
                "message": "记录不存在"
            }), 404
        
        logger.info(f"Get hotfix record detail: {record_id}")
        
        return jsonify({
            "code": 0,
            "message": "获取成功",
            "data": record
        })
        
    except Exception as e:
        logger.error(f"Failed to get hotfix record detail: {e}")
        return jsonify({
            "code": -1,
            "message": f"获取失败: {str(e)}"
        }), 500


@g.app.route('/api/hotfix/update/<record_id>', methods=['PUT'])
def update_hotfix_record(record_id: str):
    """
    更新Hotfix记录
    
    路径参数:
    - record_id: 记录ID
    
    请求体格式:
    {
        "username": "用户名",  // 可选
        "file_pairs": [...],  // 可选
        "hotfix_content": "Hotfix内容",  // 可选
        "additional_info": {}  // 可选
    }
    """
    try:
        if not record_id:
            return jsonify({
                "code": -1,
                "message": "记录ID不能为空"
            }), 400
        
        data = request.get_json()
        if not data:
            return jsonify({
                "code": -1,
                "message": "请求体不能为空"
            }), 400
        
        # 过滤允许更新的字段
        allowed_fields = ['username', 'file_pairs', 'hotfix_content', 'additional_info']
        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        
        if not update_data:
            return jsonify({
                "code": -1,
                "message": "没有可更新的字段"
            }), 400
        
        # 更新记录
        hotfix_mongo = get_hotfix_mongo()
        success = hotfix_mongo.update_hotfix_record(record_id, update_data)
        
        if not success:
            return jsonify({
                "code": -1,
                "message": "记录不存在或更新失败"
            }), 404
        
        logger.info(f"Hotfix record updated: {record_id}")
        
        return jsonify({
            "code": 0,
            "message": "更新成功"
        })
        
    except Exception as e:
        logger.error(f"Failed to update hotfix record: {e}")
        return jsonify({
            "code": -1,
            "message": f"更新失败: {str(e)}"
        }), 500


@g.app.route('/api/hotfix/delete/<record_id>', methods=['DELETE'])
def delete_hotfix_record(record_id: str):
    """
    删除Hotfix记录
    
    路径参数:
    - record_id: 记录ID
    """
    try:
        if not record_id:
            return jsonify({
                "code": -1,
                "message": "记录ID不能为空"
            }), 400
        
        # 删除记录
        hotfix_mongo = get_hotfix_mongo()
        success = hotfix_mongo.delete_hotfix_record(record_id)
        
        if not success:
            return jsonify({
                "code": -1,
                "message": "记录不存在或删除失败"
            }), 404
        
        logger.info(f"Hotfix record deleted: {record_id}")
        
        return jsonify({
            "code": 0,
            "message": "删除成功"
        })
        
    except Exception as e:
        logger.error(f"Failed to delete hotfix record: {e}")
        return jsonify({
            "code": -1,
            "message": f"删除失败: {str(e)}"
        }), 500


@g.app.route('/api/hotfix/statistics', methods=['GET'])
def get_hotfix_statistics():
    """
    获取Hotfix统计信息
    
    查询参数:
    - username: 用户名过滤（可选）
    """
    try:
        username = request.args.get('username')
        
        # 获取统计信息
        hotfix_mongo = get_hotfix_mongo()
        statistics = hotfix_mongo.get_user_statistics(username)
        
        logger.info(f"Get hotfix statistics for user: {username or 'all'}")
        
        return jsonify({
            "code": 0,
            "message": "获取统计信息成功",
            "data": statistics
        })
        
    except Exception as e:
        logger.error(f"Failed to get hotfix statistics: {e}")
        return jsonify({
            "code": -1,
            "message": f"获取统计信息失败: {str(e)}"
        }), 500
