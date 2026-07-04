# -*- coding: utf-8 -*-
"""
KDIP工具路由
提供KDIP相关的API接口
"""

from flask import request, jsonify
from appImp import app
from Implement.kdipImpl import (
    KdipClient, 
    KdipError, 
    KDIP_CMD_WHITELIST, 
    KDIP_CMD_COOLDOWN,
    DEFAULT_CMD_COOLDOWN
)
import traceback


@app.route("/api/kdip/getServerList", methods=["GET"])
def kdip_get_server_list():
    """获取服务器列表"""
    try:
        client = KdipClient(logger=app.logger)
        servers = client.get_server_list()
        return jsonify({
            "code": 200,
            "message": "success",
            "data": servers
        })
    except Exception as e:
        app.logger.error(f"[KDIP] get_server_list error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            "code": 500,
            "message": f"获取服务器列表失败: {str(e)}",
            "data": None
        }), 500


@app.route("/api/kdip/getCmdWhitelist", methods=["GET"])
def kdip_get_cmd_whitelist():
    """获取指令白名单"""
    try:
        return jsonify({
            "code": 200,
            "message": "success",
            "data": KDIP_CMD_WHITELIST
        })
    except Exception as e:
        app.logger.error(f"[KDIP] get_cmd_whitelist error: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"获取指令白名单失败: {str(e)}",
            "data": None
        }), 500


@app.route("/api/kdip/getCmdCooldown", methods=["GET"])
def kdip_get_cmd_cooldown():
    """获取指令CD配置"""
    try:
        return jsonify({
            "code": 200,
            "message": "success",
            "data": {
                "cooldown": KDIP_CMD_COOLDOWN,
                "default": DEFAULT_CMD_COOLDOWN
            }
        })
    except Exception as e:
        app.logger.error(f"[KDIP] get_cmd_cooldown error: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"获取指令CD配置失败: {str(e)}",
            "data": None
        }), 500


@app.route("/api/kdip/executeCmd", methods=["POST"])
def kdip_execute_cmd():
    """
    执行KDIP指令
    
    请求参数:
    {
        "namespace": "c7_dev",  // 服务器命名空间
        "cmd_key": "kdip_game_get_config_for_qa",  // 指令key
        "cmd_param": {},  // 指令参数（可选）
        "username": "chenzhixu"  // 用户名
    }
    """
    try:
        data = request.get_json()
        namespace = data.get("namespace")
        cmd_key = data.get("cmd_key")
        cmd_param = data.get("cmd_param", {})
        username = data.get("username")
        
        # 参数校验
        if not namespace:
            return jsonify({
                "code": 400,
                "message": "namespace不能为空",
                "data": None
            }), 400
        
        if not cmd_key:
            return jsonify({
                "code": 400,
                "message": "cmd_key不能为空",
                "data": None
            }), 400
        
        if not username:
            return jsonify({
                "code": 400,
                "message": "username不能为空",
                "data": None
            }), 400
        
        # 执行指令
        client = KdipClient(logger=app.logger)
        result = client.execute_custom_cmd(namespace, cmd_key, cmd_param, username)
        
        return jsonify({
            "code": 200,
            "message": "success",
            "data": result
        })
        
    except KdipError as e:
        app.logger.error(f"[KDIP] execute_cmd KdipError: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            "code": 400,
            "message": str(e),
            "data": None
        }), 400
    except Exception as e:
        app.logger.error(f"[KDIP] execute_cmd error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            "code": 500,
            "message": f"执行指令失败: {str(e)}",
            "data": None
        }), 500


@app.route("/api/kdip/getServerInfo", methods=["GET"])
def kdip_get_server_info():
    """
    获取服务器详细信息
    
    请求参数:
    namespace: 服务器命名空间
    """
    try:
        namespace = request.args.get("namespace")
        if not namespace:
            return jsonify({
                "code": 400,
                "message": "namespace不能为空",
                "data": None
            }), 400
        
        client = KdipClient(logger=app.logger)
        server_info = client.get_server_info(namespace)
        
        return jsonify({
            "code": 200,
            "message": "success",
            "data": server_info
        })
        
    except KdipError as e:
        app.logger.error(f"[KDIP] get_server_info error: {str(e)}")
        return jsonify({
            "code": 400,
            "message": str(e),
            "data": None
        }), 400
    except Exception as e:
        app.logger.error(f"[KDIP] get_server_info error: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"获取服务器信息失败: {str(e)}",
            "data": None
        }), 500


# 预定义的快捷指令接口
@app.route("/api/kdip/getCurrentConfig", methods=["POST"])
def kdip_get_current_config():
    """获取当前配置"""
    try:
        data = request.get_json()
        namespace = data.get("namespace")
        username = data.get("username")
        
        if not namespace or not username:
            return jsonify({
                "code": 400,
                "message": "namespace和username不能为空",
                "data": None
            }), 400
        
        client = KdipClient(logger=app.logger)
        server_info = client.get_server_info(namespace)
        result = client.get_current_config(
            server_info["zone_id"],
            server_info["server_id"],
            username
        )
        
        return jsonify({
            "code": 200,
            "message": "success",
            "data": result
        })
        
    except Exception as e:
        app.logger.error(f"[KDIP] get_current_config error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            "code": 500,
            "message": f"获取配置失败: {str(e)}",
            "data": None
        }), 500


@app.route("/api/kdip/getSwitchState", methods=["POST"])
def kdip_get_switch_state():
    """获取开关状态"""
    try:
        data = request.get_json()
        namespace = data.get("namespace")
        username = data.get("username")
        
        if not namespace or not username:
            return jsonify({
                "code": 400,
                "message": "namespace和username不能为空",
                "data": None
            }), 400
        
        client = KdipClient(logger=app.logger)
        server_info = client.get_server_info(namespace)
        result = client.get_switch_state(
            server_info["zone_id"],
            server_info["server_id"],
            username
        )
        
        return jsonify({
            "code": 200,
            "message": "success",
            "data": result
        })
        
    except Exception as e:
        app.logger.error(f"[KDIP] get_switch_state error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            "code": 500,
            "message": f"获取开关状态失败: {str(e)}",
            "data": None
        }), 500


@app.route("/api/kdip/getHotfixInfo", methods=["POST"])
def kdip_get_hotfix_info():
    """获取hotfix信息"""
    try:
        data = request.get_json()
        namespace = data.get("namespace")
        username = data.get("username")
        
        if not namespace or not username:
            return jsonify({
                "code": 400,
                "message": "namespace和username不能为空",
                "data": None
            }), 400
        
        client = KdipClient(logger=app.logger)
        server_info = client.get_server_info(namespace)
        result = client.get_hotfix_info(
            server_info["zone_id"],
            server_info["server_id"],
            username
        )
        
        return jsonify({
            "code": 200,
            "message": "success",
            "data": result
        })
        
    except Exception as e:
        app.logger.error(f"[KDIP] get_hotfix_info error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            "code": 500,
            "message": f"获取hotfix信息失败: {str(e)}",
            "data": None
        }), 500


@app.route("/api/kdip/getServerRunInfo", methods=["POST"])
def kdip_get_server_run_info():
    """获取服务器运行信息"""
    try:
        data = request.get_json()
        namespace = data.get("namespace")
        username = data.get("username")
        
        if not namespace or not username:
            return jsonify({
                "code": 400,
                "message": "namespace和username不能为空",
                "data": None
            }), 400
        
        client = KdipClient(logger=app.logger)
        server_info = client.get_server_info(namespace)
        result = client.get_server_run_info(
            server_info["zone_id"],
            server_info["server_id"],
            username
        )
        
        return jsonify({
            "code": 200,
            "message": "success",
            "data": result
        })
        
    except Exception as e:
        app.logger.error(f"[KDIP] get_server_run_info error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            "code": 500,
            "message": f"获取服务器运行信息失败: {str(e)}",
            "data": None
        }), 500


@app.route("/api/kdip/getStallMetricInfo", methods=["POST"])
def kdip_get_stall_metric_info():
    """获取交易行信息"""
    try:
        data = request.get_json()
        namespace = data.get("namespace")
        username = data.get("username")
        
        if not namespace or not username:
            return jsonify({
                "code": 400,
                "message": "namespace和username不能为空",
                "data": None
            }), 400
        
        client = KdipClient(logger=app.logger)
        server_info = client.get_server_info(namespace)
        result = client.get_stall_metric_info(
            server_info["zone_id"],
            server_info["server_id"],
            username
        )
        
        return jsonify({
            "code": 200,
            "message": "success",
            "data": result
        })
        
    except Exception as e:
        app.logger.error(f"[KDIP] get_stall_metric_info error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            "code": 500,
            "message": f"获取交易行信息失败: {str(e)}",
            "data": None
        }), 500
