# WorkFlow REST API Routes

# builtin
from datetime import datetime
import os
import uuid
import subprocess
import re
import threading
import time
import asyncio
import logging

# 3rd ext
from flask import render_template, request, jsonify, Response
from sqlalchemy import and_
import io
import csv

# int
from appImp import app
from Implement.hotfixImpl import p4Imp
from Implement.hotfixImpl import hotfixImp
from utility import p4Utils
import config
import json
from managers.timeMgr import cron

# WorkFlow implementation
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

logger.info("[WorkFlow] All node executors registered: %s", ExecutorManager.list_executors())

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
        workflow_id = data.get('id')  # Optional for updates
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
    logger.info("[workflow_get] Request for workflow_id=%r from %s", workflow_id, request.remote_addr)
    try:
        workflow = WorkflowManager.get(workflow_id)
        if not workflow:
            logger.warning("[workflow_get] Workflow not found: id=%r", workflow_id)
            return jsonify({'error': 'Workflow not found'}), 404
        logger.info("[workflow_get] Found workflow: id=%r, name=%r", workflow_id, workflow.get('name'))
        return jsonify(workflow)
    except Exception as e:
        logger.exception("[workflow_get] Unexpected error for workflow_id=%r: %s", workflow_id, e)
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
    """Delete a workflow"""
    logger.info("[workflow_delete] Request for workflow_id=%r from %s", workflow_id, request.remote_addr)
    try:
        success = WorkflowManager.delete(workflow_id)
        if not success:
            logger.warning("[workflow_delete] Workflow not found: id=%r", workflow_id)
            return jsonify({'error': 'Workflow not found'}), 404
        logger.info("[workflow_delete] Deleted workflow: id=%r", workflow_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("[workflow_delete] Unexpected error for workflow_id=%r: %s", workflow_id, e)
        return jsonify({'error': str(e)}), 500


# endregion


# region Node Execution APIs

@app.route('/api/workflow/node/run', methods=['POST'])
def workflow_node_run():
    """Run a single node (no downstream cascade; cascade is handled by the frontend)"""
    logger.info("[workflow_node_run] Request received from %s", request.remote_addr)
    try:
        data = request.json
        node_type = data.get('type')
        config_data = data.get('config', {})
        input_data = data.get('input', {})

        logger.info("[workflow_node_run] node_type=%r, config_keys=%s, input_keys=%s",
                    node_type, list(config_data.keys()), list(input_data.keys()))

        if not node_type:
            logger.warning("[workflow_node_run] Missing required field: type")
            return jsonify({'error': 'type is required'}), 400

        # Executors are synchronous — call directly, no asyncio/threading needed
        output = ExecutorManager.run_node(node_type, config_data, input_data)

        if isinstance(output, dict) and output.get('error'):
            logger.warning("[workflow_node_run] Executor returned error for node_type=%r: %s", node_type, output['error'])
        else:
            logger.info("[workflow_node_run] node_type=%r executed successfully, output_keys=%s",
                        node_type, list(output.keys()) if isinstance(output, dict) else type(output).__name__)

        return jsonify({'output': output})
    except Exception as e:
        logger.exception("[workflow_node_run] Unexpected error for node_type=%r: %s", data.get('type') if data else None, e)
        return jsonify({'error': str(e)}), 500


# endregion


# region Workflow Execution APIs

@app.route('/api/workflow/run', methods=['POST'])
def workflow_run():
    """Run an entire workflow (DAG).
    
    Execution strategy:
    - Root nodes (no incoming edges) are all executed concurrently in parallel.
    - Downstream nodes wait until ALL their upstream dependencies finish.
    - Shared nodes (common dependencies) are executed exactly once, after all
      their upstream root nodes have completed.
    """
    logger.info("[workflow_run] Request received from %s", request.remote_addr)
    try:
        data = request.json
        workflow_id = data.get('workflowId')

        logger.info("[workflow_run] workflowId=%r", workflow_id)

        if not workflow_id:
            logger.warning("[workflow_run] Missing required field: workflowId")
            return jsonify({'error': 'workflowId is required'}), 400

        # Get workflow
        workflow = WorkflowManager.get(workflow_id)
        if not workflow:
            logger.warning("[workflow_run] Workflow not found: id=%r", workflow_id)
            return jsonify({'error': 'Workflow not found'}), 404

        workflow_json = workflow.get('json')
        nodes = workflow_json.get('nodes', []) if isinstance(workflow_json, dict) else []
        edges = workflow_json.get('edges', []) if isinstance(workflow_json, dict) else []
        logger.info("[workflow_run] Workflow loaded: name=%r, nodes=%d, edges=%d",
                    workflow.get('name'), len(nodes), len(edges))

        # Run workflow in background thread
        task_id = str(uuid.uuid4())
        logger.info("[workflow_run] Starting background task: task_id=%r", task_id)

        def run_workflow():
            logger.info("[workflow_run] Background thread started: task_id=%r", task_id)
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    WorkflowRuntime.run(workflow_json, task_id)
                )
                loop.close()
                logger.info("[workflow_run] Background thread completed: task_id=%r", task_id)
            except Exception as e:
                logger.exception("[workflow_run] Background thread error: task_id=%r, error=%s", task_id, e)

        thread = threading.Thread(target=run_workflow, daemon=True)
        thread.start()

        logger.info("[workflow_run] Background thread started, returning task_id=%r", task_id)
        return jsonify({'taskId': task_id})
    except Exception as e:
        logger.exception("[workflow_run] Unexpected error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/run/<task_id>/status', methods=['GET'])
def workflow_run_status(task_id):
    """Get workflow execution status"""
    logger.debug("[workflow_run_status] Querying task_id=%r from %s", task_id, request.remote_addr)
    try:
        task = WorkflowRuntime.get_task_status(task_id)
        if not task:
            logger.warning("[workflow_run_status] Task not found: task_id=%r", task_id)
            return jsonify({'error': 'Task not found'}), 404
        logger.debug("[workflow_run_status] task_id=%r, status=%r, node_count=%d",
                     task_id, task.get('status'), len(task.get('nodes', {})))
        return jsonify(task)
    except Exception as e:
        logger.exception("[workflow_run_status] Unexpected error for task_id=%r: %s", task_id, e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/run/<task_id>/cancel', methods=['POST'])
def workflow_run_cancel(task_id):
    """Cancel a running workflow"""
    logger.info("[workflow_run_cancel] Request for task_id=%r from %s", task_id, request.remote_addr)
    try:
        success = WorkflowRuntime.cancel_task(task_id)
        if not success:
            logger.warning("[workflow_run_cancel] Task not found or not running: task_id=%r", task_id)
            return jsonify({'error': 'Task not found or not running'}), 404
        logger.info("[workflow_run_cancel] Task canceled: task_id=%r", task_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("[workflow_run_cancel] Unexpected error for task_id=%r: %s", task_id, e)
        return jsonify({'error': str(e)}), 500


# endregion


# region Executor Management APIs

@app.route('/api/workflow/executors', methods=['GET'])
def workflow_executors():
    """List all registered node executors"""
    logger.info("[workflow_executors] Request from %s", request.remote_addr)
    try:
        executors = ExecutorManager.list_executors()
        logger.info("[workflow_executors] Returning %d executors: %s", len(executors), executors)
        return jsonify({'executors': executors})
    except Exception as e:
        logger.exception("[workflow_executors] Unexpected error: %s", e)
        return jsonify({'error': str(e)}), 500


# endregion
