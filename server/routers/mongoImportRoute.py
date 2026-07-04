from flask import request, jsonify, send_file
from werkzeug.utils import secure_filename

import g
from appImp import app
from Implement.pickImpl import pickImp

@g.app.route('/migrate', methods=['POST'])
def mongo_migrate():
    """
    统一的数据迁移接口 (导出 + 导入)
    
    前端只需调用这一个接口,后端自动完成:
    1. 导出源环境数据
    2. 导入到目标环境
    """
    try:
        data = request.get_json()
        
        # 获取参数
        source_env = data.get('sourceEnv', 'local')
        source_logic_id = data.get('sourceLogicId')
        target_env = data.get('targetEnv', 'local')
        target_logic_id = data.get('targetLogicId')
        export_avatar_ids = data.get('exportAvatarIds', [])
        export_avatar_names = data.get('exportAvatarNames', [])
        short_uid = data.get('shortUid', '')
        dest_account = data.get('destAccount', '')
        operator = data.get('operator', 'unknown')
        regen_avatar_id = bool(data.get('regenAvatarId', False))
        
        # 参数验证
        if not source_logic_id:
            return jsonify({
                'code': 1,
                'errMsg': '源 Logic Server ID 不能为空'
            })
        
        if not target_logic_id:
            return jsonify({
                'code': 1,
                'errMsg': '目标 Logic Server ID 不能为空'
            })
        
        if not export_avatar_ids and not short_uid:
            return jsonify({
                'code': 1,
                'errMsg': '角色ID和ShortUid不能同时为空'
            })
        
        app.logger.info(f"Starting migration: {source_env}/{source_logic_id} -> {target_env}/{target_logic_id}, "
                   f"ids={export_avatar_ids}, names={export_avatar_names}")
        
        # 判断环境组合
        if source_env == 'local' and target_env == 'local':
            ret = pickImp.local_to_local(source_logic_id, target_logic_id, dest_account, export_avatar_ids, short_uid, regen_avatar_id)
            return jsonify(ret)
        elif source_env == 'local' and target_env == 'test':
            ret = pickImp.local_to_test(source_logic_id, target_logic_id, dest_account, export_avatar_ids, short_uid, regen_avatar_id)
            return jsonify(ret)
        elif source_env == 'test' and target_env == 'local':
            ret = pickImp.test_to_local(source_logic_id, target_logic_id, dest_account, export_avatar_ids, short_uid, regen_avatar_id)
            return jsonify(ret)
        elif source_env == 'test' and target_env == 'test':
            ret = pickImp.test_to_test(source_logic_id, target_logic_id, dest_account, export_avatar_ids, short_uid, regen_avatar_id)
            return jsonify(ret)
        elif source_env == 'weekly' and target_env == 'local':
            ret = pickImp.weekly_to_local(source_logic_id, target_logic_id, dest_account, export_avatar_ids, short_uid, regen_avatar_id)
            return jsonify(ret)
        elif source_env == 'weekly' and target_env == 'test':
            ret = pickImp.weekly_to_test(source_logic_id, target_logic_id, dest_account, export_avatar_ids, short_uid, regen_avatar_id)
            return jsonify(ret)
        else:
            return jsonify({
                'code': 1,
                'errMsg': f'暂不支持 {source_env} -> {target_env} 的迁移,目前仅支持 local/test -> local/test, weekly -> local/test'
            })
        
    except Exception as e:
        app.logger.error(f"mongo_migrate error: {e}", exc_info=True)
        return jsonify({
            'code': 1,
            'errMsg': str(e)
        }), 500

@g.app.route('/history', methods=['GET'])
def get_history():
    """获取操作历史记录"""
    try:
        ret = pickImp.get_history()
        return jsonify(ret)
    
    except Exception as e:
        app.logger.error(f"get_history error: {e}", exc_info=True)
        return jsonify({
            'code': 1,
            'errMsg': str(e)
        }), 500

@g.app.route('/history/dump', methods=['POST'])
def get_dump_file():
    """获取历史dump文件内容"""
    try:
        date = request.get_json()
        filename = date.get('filename', '')
        ret = pickImp.get_dump_file(filename)
        return jsonify(ret)
    
    except Exception as e:
        app.logger.error(f"get_dump_file error: {e}", exc_info=True)
        return jsonify({
            'code': 1,
            'errMsg': str(e)
        }), 500
    
@g.app.route('/config/local_servers', methods=['GET'])
def get_local_servers():
    """获取指定环境的Local Server列表"""
    try:
        ret = pickImp.get_local_server()
        return jsonify(ret)
    
    except Exception as e:
        app.logger.error(f"get_local_servers error: {e}", exc_info=True)
        return jsonify({
            'code': 1,
            'errMsg': str(e)
        }), 500

@g.app.route('/config/test_servers', methods=['GET'])
def get_test_servers():
    """获取指定环境的云私服 Server列表"""
    try:
        ret = pickImp.get_test_server()
        return jsonify(ret)
    
    except Exception as e:
        app.logger.error(f"get_test_servers error: {e}", exc_info=True)
        return jsonify({
            'code': 1,
            'errMsg': str(e)
        }), 500

@g.app.route('/config/logic_servers', methods=['GET'])
def get_logic_servers():
    """获取指定环境的Logic Server列表"""
    try:
        ret = pickImp.get_logic_server()
        return jsonify(ret)
    
    except Exception as e:
        app.logger.error(f"get_logic_servers error: {e}", exc_info=True)
        return jsonify({
            'code': 1,
            'errMsg': str(e)
        }), 500
    
@g.app.route('/config/request_config', methods=['GET'])
def get_request_config():
    """获取请求配置"""
    try:
        ret = pickImp.request_config()
        return jsonify(ret)
    
    except Exception as e:
        app.logger.error(f"get_request_config error: {e}", exc_info=True)
        return jsonify({
            'code': 1,
            'errMsg': str(e)
        }), 500
    
@g.app.route('/config/upload_local_config', methods=['POST'])
def upload_local_config():
    """上传单个本地服务器配置到 local_conf.json"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        hosts = data.get('hosts', [])
        alias = data.get('alias', '').strip()
        
        if not name:
            return jsonify({
                'code': 1,
                'errMsg': '服务器名称不能为空'
            })
        
        # 调用后端函数保存配置（hosts可以为空，后端会提供默认值）
        ret = pickImp.upload_local_config(name, hosts, alias)
        return jsonify(ret)
    
    except Exception as e:
        app.logger.error(f"upload_local_config error: {e}", exc_info=True)
        return jsonify({
            'code': 1,
            'errMsg': str(e)
        }), 500
    
@g.app.route('/config/delete_local_config', methods=['POST'])
def delete_local_config():
    """从 local_conf.json 中删除指定的本地服务器配置"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()

        if not name:
            return jsonify({
                'code': 1,
                'errMsg': '服务器名称不能为空'
            })

        ret = pickImp.delete_local_config(name)
        return jsonify(ret)

    except Exception as e:
        app.logger.error(f"delete_local_config error: {e}", exc_info=True)
        return jsonify({
            'code': 1,
            'errMsg': str(e)
        }), 500