# WorkFlow REST API Routes

# builtin
from datetime import datetime
import os
import uuid
import asyncio
import json
import logging

# 3rd ext
from flask import request, jsonify
from flask_socketio import join_room, leave_room

# int
from appImp import app, socketio
from Implement.workflowImpl.workflowImp import WorkflowManager, WorkflowRuntime
from Implement.workflowImpl.nodeExecutor import ExecutorManager
from Implement.workflowImpl.excelExecutor import ExcelExecutor
from Implement.workflowImpl.luaExecutor import LuaExecutor
from Implement.workflowImpl.jsonExecutor import JsonExecutor
from Implement.workflowImpl.promptExecutor import PromptExecutor
from Implement.workflowImpl.p4FileExecutor import P4FileExecutor
from Implement.workflowImpl.stringExecutor import StringExecutor
from Implement.workflowImpl.boolExecutor import BoolExecutor
from Implement.workflowImpl.numberExecutor import NumberExecutor
from Implement.workflowImpl.diffExecutor import DiffExecutor
from Implement.workflowImpl.c7ServerExecutor import C7ServerExecutor, _load_c7_server_list
from Implement.workflowImpl.kdipExecutor import KdipExecutor
from Implement.workflowImpl.kimNotifyExecutor import KimNotifyExecutor
from Implement.workflowImpl.boolGateExecutor import BoolGateExecutor
from Implement.workflowImpl.tableExecutor import TableExecutor
from Implement.workflowImpl.excelSearchExecutor import ExcelSearchExecutor, load_excelsearch_options
from Implement.workflowImpl.cronExecutor import CronExecutor, CronRegistry
from Implement.workflowImpl.setGlobalValueExecutor import SetGlobalValueExecutor
from Implement.workflowImpl.getGlobalValueExecutor import GetGlobalValueExecutor
from Implement.workflowImpl.mergeObjectExecutor import MergeObjectExecutor

# Shared Redis key constants for global variable management
from Implement.workflowImpl.setGlobalValueExecutor import WF_GVAR_PREFIX, WF_GVAR_REGISTRY

# region init

logger = logging.getLogger(__name__)

# Register all node executors
ExecutorManager.register(ExcelExecutor())
ExecutorManager.register(LuaExecutor())
ExecutorManager.register(JsonExecutor())
ExecutorManager.register(PromptExecutor())
ExecutorManager.register(P4FileExecutor())
ExecutorManager.register(StringExecutor())
ExecutorManager.register(BoolExecutor())
ExecutorManager.register(NumberExecutor())
ExecutorManager.register(DiffExecutor())
ExecutorManager.register(C7ServerExecutor())
ExecutorManager.register(KdipExecutor())
ExecutorManager.register(KimNotifyExecutor())
ExecutorManager.register(BoolGateExecutor())
ExecutorManager.register(TableExecutor())
ExecutorManager.register(ExcelSearchExecutor())
ExecutorManager.register(CronExecutor())
ExecutorManager.register(SetGlobalValueExecutor())
ExecutorManager.register(GetGlobalValueExecutor())
ExecutorManager.register(MergeObjectExecutor())

logger.info("[WorkFlow] All node executors registered: %s", ExecutorManager.list_executors())

# endregion


# region Cron Management APIs

@app.route('/api/workflow/cron/start', methods=['POST'])
def cron_start():
    """Start a new cron schedule.
    Body: { cronExpr, workflowId, nodeId }
    Returns: { success, cronId, message } or { error }
    """
    try:
        data = request.json
        cron_expr = data.get('cronExpr', '').strip()
        workflow_id = data.get('workflowId', '')
        node_id = data.get('nodeId', '')

        if not cron_expr:
            return jsonify({'error': 'Cron 表达式不能为空'}), 400

        output = ExecutorManager.run_node('cron', {
            'cronExpr': cron_expr,
            'workflowId': workflow_id,
            'nodeId': node_id,
        }, {})

        if output.get('error'):
            return jsonify({'error': output['error']}), 400

        # Set callback to trigger downstream execution via Socket.IO
        cron_id = output.get('cronId')
        if cron_id:
            def _cron_callback():
                """When cron fires, emit a Socket.IO event to trigger downstream nodes."""
                logger.info("[CronCallback] cron_id=%s firing, emitting workflow:cron_fire", cron_id)
                socketio.emit('workflow:cron_fire', {
                    'cronId': cron_id,
                    'workflowId': workflow_id,
                    'nodeId': node_id,
                    'timestamp': datetime.now().isoformat(),
                }, room=workflow_id)

            with CronRegistry.instance()._lock:
                entry = CronRegistry.instance()._crons.get(cron_id)
                if entry:
                    entry['callback'] = _cron_callback

        return jsonify(output)
    except Exception as e:
        logger.exception("[cron_start] Error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/cron/list', methods=['GET'])
def cron_list():
    """List all registered cron jobs (running and recently stopped)."""
    try:
        CronRegistry.instance().cleanup_stopped()
        return jsonify({'crons': CronRegistry.instance().list_all()})
    except Exception as e:
        logger.exception("[cron_list] Error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/cron/<cron_id>/stop', methods=['POST'])
def cron_stop(cron_id):
    """Stop a running cron job."""
    try:
        ok = CronRegistry.instance().stop(cron_id)
        if not ok:
            return jsonify({'error': f'Cron {cron_id} 不存在或已停止'}), 404
        return jsonify({'success': True, 'cronId': cron_id, 'message': f'Cron {cron_id} 已停止'})
    except Exception as e:
        logger.exception("[cron_stop] Error: %s", e)
        return jsonify({'error': str(e)}), 500

# endregion


# region Global Variable Management API

@app.route('/api/workflow/vars/list', methods=['GET'])
def vars_list():
    """List all workflow global variables with current value and updated_at."""
    try:
        from dbImp.redisImp import my_redis
        registry = my_redis.hgetall(WF_GVAR_REGISTRY)
        result = []
        for key_b, meta_b in registry.items():
            key = key_b if isinstance(key_b, str) else key_b.decode('utf-8')
            meta_str = meta_b if isinstance(meta_b, str) else meta_b.decode('utf-8')
            try:
                meta = json.loads(meta_str)
            except Exception:
                meta = {}
            redis_key = f"{WF_GVAR_PREFIX}{key}"
            val = my_redis.get(redis_key)
            result.append({
                'key': key,
                'value': val if isinstance(val, str) else (val.decode('utf-8') if val else None),
                'updated_at': meta.get('updated_at', ''),
            })
        return jsonify({'vars': result})
    except Exception as e:
        logger.exception("[vars_list] Error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/vars/set', methods=['POST'])
def vars_set():
    """Manually set a global variable."""
    data = request.get_json(silent=True) or {}
    key = str(data.get('key', '')).strip()
    value = str(data.get('value', '')) if data.get('value') is not None else ''
    if not key:
        return jsonify({'error': 'Key 不能为空'}), 400
    try:
        from dbImp.redisImp import my_redis
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        pipe = my_redis.pipeline()
        pipe.set(f"{WF_GVAR_PREFIX}{key}", value)
        pipe.hset(WF_GVAR_REGISTRY, key, json.dumps({"updated_at": now}))
        pipe.execute()
        return jsonify({'success': True, 'key': key})
    except Exception as e:
        logger.exception("[vars_set] Error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/vars/delete', methods=['POST'])
def vars_delete():
    """Delete a global variable."""
    data = request.get_json(silent=True) or {}
    key = str(data.get('key', '')).strip()
    if not key:
        return jsonify({'error': 'Key 不能为空'}), 400
    try:
        from dbImp.redisImp import my_redis
        pipe = my_redis.pipeline()
        pipe.delete(f"{WF_GVAR_PREFIX}{key}")
        pipe.hdel(WF_GVAR_REGISTRY, key)
        pipe.execute()
        return jsonify({'success': True, 'key': key})
    except Exception as e:
        logger.exception("[vars_delete] Error: %s", e)
        return jsonify({'error': str(e)}), 500

# endregion


# region Socket.IO Events

@socketio.on('connect')
def on_connect():
    logger.info("[SocketIO] Client connected: sid=%s", request.sid)


@socketio.on('disconnect')
def on_disconnect():
    logger.info("[SocketIO] Client disconnected: sid=%s", request.sid)


@socketio.on('workflow:join')
def on_workflow_join(data):
    """Client joins a task room to receive workflow execution events."""
    task_id = data.get('taskId')
    if task_id:
        join_room(task_id)
        logger.info("[SocketIO] sid=%s joined room: task_id=%r", request.sid, task_id)
        socketio.emit('workflow:joined', {'taskId': task_id}, room=request.sid)


@socketio.on('workflow:leave')
def on_workflow_leave(data):
    """Client leaves a task room."""
    task_id = data.get('taskId')
    if task_id:
        leave_room(task_id)
        logger.info("[SocketIO] sid=%s left room: task_id=%r", request.sid, task_id)


@socketio.on('workflow:run')
def on_workflow_run(data):
    """Start a workflow run via Socket.IO.

    Client sends: { workflowId }
    Server emits:
      - workflow:started      { taskId }
      - workflow:node_update  { taskId, nodeId, status, output }
      - workflow:done         { taskId, status, error }
    """
    workflow_id = data.get('workflowId')
    logger.info("[SocketIO workflow:run] sid=%s, workflowId=%r", request.sid, workflow_id)

    if not workflow_id:
        socketio.emit('workflow:error', {'error': 'workflowId is required'}, room=request.sid)
        return

    workflow = WorkflowManager.get(workflow_id)
    if not workflow:
        socketio.emit('workflow:error', {'error': f'Workflow not found: {workflow_id}'}, room=request.sid)
        return

    workflow_json = workflow.get('json')
    nodes = workflow_json.get('nodes', []) if isinstance(workflow_json, dict) else []
    edges = workflow_json.get('edges', []) if isinstance(workflow_json, dict) else []

    task_id = str(uuid.uuid4())
    logger.info("[SocketIO workflow:run] task_id=%r, nodes=%d, edges=%d, workflow=%r",
                task_id, len(nodes), len(edges), workflow.get('name'))

    # Client automatically joins the task room
    join_room(task_id)
    logger.info("[SocketIO workflow:run] sid=%s auto-joined room task_id=%r", request.sid, task_id)

    # Notify client of task_id immediately
    socketio.emit('workflow:started', {'taskId': task_id}, room=request.sid)

    def run_workflow():
        logger.info("[SocketIO workflow:run] Background task started: task_id=%r", task_id)
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(WorkflowRuntime.run(workflow_json, task_id))
            loop.close()
            logger.info("[SocketIO workflow:run] Background task completed: task_id=%r", task_id)
        except Exception as e:
            logger.exception("[SocketIO workflow:run] Background task error: task_id=%r, %s", task_id, e)
            socketio.emit('workflow:done', {
                'taskId': task_id, 'status': 'error', 'error': str(e)
            }, room=task_id)

    # Run in socketio background task (gevent greenlet)
    socketio.start_background_task(run_workflow)


@socketio.on('workflow:run_from_node')
def on_workflow_run_from_node(data) -> None:
    """Run a subgraph starting from a specific node via Socket.IO.

    Client sends:
      {
        workflowId,        # required
        startNodeId,       # required: the node to start from
        nodeDataOverrides, # optional: { nodeId: { fieldKey: value, ... } }
                           #   - for the start node: its latest field values (may not be saved yet)
                           #   - for upstream nodes: their last known _runOutput to use as context
      }
    Server emits:
      - workflow:started      { taskId }
      - workflow:node_update  { taskId, nodeId, status, output }
      - workflow:done         { taskId, status, error }
    """
    workflow_id = data.get('workflowId')
    start_node_id = data.get('startNodeId')
    node_data_overrides = data.get('nodeDataOverrides') or {}

    logger.info("[SocketIO workflow:run_from_node] sid=%s, workflowId=%r, startNodeId=%r",
                request.sid, workflow_id, start_node_id)

    if not workflow_id or not start_node_id:
        socketio.emit('workflow:error', {'error': 'workflowId and startNodeId are required'}, room=request.sid)
        return

    workflow = WorkflowManager.get(workflow_id)
    if not workflow:
        socketio.emit('workflow:error', {'error': f'Workflow not found: {workflow_id}'}, room=request.sid)
        return

    workflow_json = workflow.get('json')
    nodes = workflow_json.get('nodes', []) if isinstance(workflow_json, dict) else []
    edges = workflow_json.get('edges', []) if isinstance(workflow_json, dict) else []

    task_id = str(uuid.uuid4())
    logger.info("[SocketIO workflow:run_from_node] task_id=%r, nodes=%d, edges=%d, startNode=%r",
                task_id, len(nodes), len(edges), start_node_id)

    # Client automatically joins the task room
    join_room(task_id)
    logger.info("[SocketIO workflow:run_from_node] sid=%s auto-joined room task_id=%r", request.sid, task_id)

    # Notify client of task_id immediately
    socketio.emit('workflow:started', {'taskId': task_id}, room=request.sid)

    def run_subgraph():
        logger.info("[SocketIO workflow:run_from_node] Background task started: task_id=%r, startNode=%r",
                    task_id, start_node_id)
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                WorkflowRuntime.run(
                    workflow_json,
                    task_id,
                    start_node_id=start_node_id,
                    node_data_overrides=node_data_overrides,
                )
            )
            loop.close()
            logger.info("[SocketIO workflow:run_from_node] Background task completed: task_id=%r", task_id)
        except Exception as e:
            logger.exception("[SocketIO workflow:run_from_node] Background task error: task_id=%r, %s", task_id, e)
            socketio.emit('workflow:done', {
                'taskId': task_id, 'status': 'error', 'error': str(e)
            }, room=task_id)

    socketio.start_background_task(run_subgraph)


@socketio.on('workflow:cancel')
def on_workflow_cancel(data):
    """Cancel a running workflow via Socket.IO."""
    task_id = data.get('taskId')
    logger.info("[SocketIO workflow:cancel] sid=%s, task_id=%r", request.sid, task_id)
    if not task_id:
        socketio.emit('workflow:error', {'error': 'taskId is required'}, room=request.sid)
        return
    success = WorkflowRuntime.cancel_task(task_id)
    if not success:
        socketio.emit('workflow:error', {'error': 'Task not found or not running'}, room=request.sid)

# endregion


# region Workflow CRUD APIs

@app.route('/api/workflow/save', methods=['POST'])
def workflow_save():
    """Save or update a workflow"""
    logger.info("[workflow_save] Request received from %s", request.remote_addr)
    try:
        data = request.json
        name = data.get('name')
        workflow_json = data.get('json')
        workflow_id = data.get('id')
        author = data.get('author', '')
        description = data.get('description', '')

        logger.info("[workflow_save] name=%r, id=%r, author=%r", name, workflow_id, author)

        if not name or not workflow_json:
            logger.warning("[workflow_save] Missing required fields: name=%r, json_present=%s", name, bool(workflow_json))
            return jsonify({'error': 'name and json are required'}), 400

        result = WorkflowManager.save(name, workflow_json, workflow_id, author=author, description=description)
        logger.info("[workflow_save] Saved successfully: id=%r, name=%r", result.get('id'), result.get('name'))
        return jsonify(result)
    except Exception as e:
        logger.exception("[workflow_save] Unexpected error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/<workflow_id>', methods=['GET'])
def workflow_get(workflow_id):
    """Get a workflow by ID"""
    logger.info("[workflow_get] Request for workflow_id=%r", workflow_id)
    try:
        workflow = WorkflowManager.get(workflow_id)
        if not workflow:
            logger.warning("[workflow_get] Workflow not found: id=%r", workflow_id)
            return jsonify({'error': 'Workflow not found'}), 404
        logger.info("[workflow_get] Found workflow: id=%r, name=%r", workflow_id, workflow.get('name'))
        return jsonify(workflow)
    except Exception as e:
        logger.exception("[workflow_get] Unexpected error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/list', methods=['GET'])
def workflow_list():
    """List all workflows"""
    logger.info("[workflow_list] Request from %s", request.remote_addr)
    try:
        workflows = WorkflowManager.list_all()
        logger.info("[workflow_list] Returning %d workflows", len(workflows))
        return jsonify({'list': workflows})
    except Exception as e:
        logger.exception("[workflow_list] Unexpected error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/<workflow_id>', methods=['DELETE'])
def workflow_delete(workflow_id):
    """Move a workflow to trash"""
    logger.info("[workflow_delete] Request for workflow_id=%r", workflow_id)
    try:
        success = WorkflowManager.delete(workflow_id)
        if not success:
            logger.warning("[workflow_delete] Workflow not found: id=%r", workflow_id)
            return jsonify({'error': 'Workflow not found'}), 404
        logger.info("[workflow_delete] Moved to trash: id=%r", workflow_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("[workflow_delete] Unexpected error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/<workflow_id>/duplicate', methods=['POST'])
def workflow_duplicate(workflow_id):
    """Duplicate a workflow with a new name"""
    body = request.get_json(force=True, silent=True) or {}
    new_name = (body.get('name') or '').strip()
    if not new_name:
        return jsonify({'error': 'name is required'}), 400
    try:
        result = WorkflowManager.duplicate(workflow_id, new_name)
        if not result:
            return jsonify({'error': 'Source workflow not found'}), 404
        return jsonify({'success': True, 'id': result['id'], 'name': result['name']})
    except Exception as e:
        logger.exception("[workflow_duplicate] Unexpected error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/trash/list', methods=['GET'])
def workflow_trash_list():
    """List all workflows in trash"""
    try:
        items = WorkflowManager.list_trash()
        return jsonify({'list': items})
    except Exception as e:
        logger.exception("[workflow_trash_list] Unexpected error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/trash/<workflow_id>/restore', methods=['POST'])
def workflow_trash_restore(workflow_id):
    """Restore a workflow from trash"""
    try:
        success = WorkflowManager.restore(workflow_id)
        if not success:
            return jsonify({'error': 'Workflow not found in trash'}), 404
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("[workflow_trash_restore] Unexpected error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/trash/<workflow_id>/purge', methods=['DELETE'])
def workflow_trash_purge(workflow_id):
    """Permanently delete a workflow from trash"""
    try:
        success = WorkflowManager.purge(workflow_id)
        if not success:
            return jsonify({'error': 'Workflow not found in trash'}), 404
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("[workflow_trash_purge] Unexpected error: %s", e)
        return jsonify({'error': str(e)}), 500

# endregion


# region Node Execution APIs (single node, for direct node-run button)

@app.route('/api/workflow/node/run', methods=['POST'])
def workflow_node_run():
    """Run a single node synchronously and return output directly.
    Used by the node-level ▶ run button (single node, no DAG cascade).
    """
    logger.info("[workflow_node_run] Request from %s", request.remote_addr)
    try:
        data = request.json
        node_type = data.get('type')
        config_data = data.get('config', {})
        input_data = data.get('input', {})

        logger.info("[workflow_node_run] node_type=%r, config_keys=%s, input_keys=%s",
                    node_type, list(config_data.keys()), list(input_data.keys()))

        if not node_type:
            return jsonify({'error': 'type is required'}), 400

        output = ExecutorManager.run_node(node_type, config_data, input_data)

        if isinstance(output, dict) and output.get('error'):
            logger.warning("[workflow_node_run] Executor error for node_type=%r: %s", node_type, output['error'])
        else:
            logger.info("[workflow_node_run] node_type=%r success, output_keys=%s",
                        node_type, list(output.keys()) if isinstance(output, dict) else type(output).__name__)

        return jsonify({'output': output})
    except Exception as e:
        logger.exception("[workflow_node_run] Unexpected error: %s", e)
        return jsonify({'error': str(e)}), 500

# endregion


# region Node Data APIs

@app.route('/api/workflow/c7server/list', methods=['GET'])
def workflow_c7server_list():
    """Get C7 server and server group list for dropdown options"""
    try:
        options = _load_c7_server_list()
        return jsonify({'options': options})
    except Exception as e:
        logger.exception("[workflow_c7server_list] Error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/excelsearch/list', methods=['GET'])
def workflow_excelsearch_list():
    """Get Excel file list for ExcelSearch node dropdown"""
    try:
        options = load_excelsearch_options()
        return jsonify({'options': options})
    except Exception as e:
        logger.exception("[workflow_excelsearch_list] Error: %s", e)
        return jsonify({'error': str(e)}), 500

# endregion


# region Workflow Status APIs (REST fallback / debugging)

@app.route('/api/workflow/run/<task_id>/status', methods=['GET'])
def workflow_run_status(task_id):
    """Get workflow execution status (REST fallback for debugging)"""
    try:
        task = WorkflowRuntime.get_task_status(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        return jsonify(task)
    except Exception as e:
        logger.exception("[workflow_run_status] Unexpected error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/executors', methods=['GET'])
def workflow_executors():
    """List all registered node executors"""
    try:
        executors = ExecutorManager.list_executors()
        return jsonify({'executors': executors})
    except Exception as e:
        logger.exception("[workflow_executors] Unexpected error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/check_name', methods=['GET'])
def workflow_check_name():
    """Check if a workflow name is already taken.
    Query params:
      name     - the name to check (required)
      exclude  - workflow id to exclude from the check (optional, for renames)
    Returns: { exists: bool }
    """
    name = (request.args.get('name') or '').strip()
    exclude_id = (request.args.get('exclude') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    try:
        all_wf = WorkflowManager.list_all()
        exists = any(
            r['name'] == name and r['id'] != exclude_id
            for r in all_wf
        )
        return jsonify({'exists': exists})
    except Exception as e:
        logger.exception("[workflow_check_name] Unexpected error: %s", e)
        return jsonify({'error': str(e)}), 500

# endregion
