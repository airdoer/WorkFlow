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

# Register all node executors
ExecutorManager.register(ExcelExecutor())
ExecutorManager.register(LuaExecutor())
ExecutorManager.register(JsonExecutor())
ExecutorManager.register(PromptExecutor())
ExecutorManager.register(P4FileExecutor())
ExecutorManager.register(StringExecutor())
ExecutorManager.register(BoolExecutor())
ExecutorManager.register(NumberExecutor())

# endregion


# region Workflow CRUD APIs

@app.route('/api/workflow/save', methods=['POST'])
def workflow_save():
    """Save or update a workflow"""
    try:
        data = request.json
        name = data.get('name')
        workflow_json = data.get('json')
        workflow_id = data.get('id')  # Optional for updates
        author = data.get('author', '')
        description = data.get('description', '')
        
        if not name or not workflow_json:
            return jsonify({'error': 'name and json are required'}), 400
        
        result = WorkflowManager.save(name, workflow_json, workflow_id, author=author, description=description)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/<workflow_id>', methods=['GET'])
def workflow_get(workflow_id):
    """Get a workflow by ID"""
    try:
        workflow = WorkflowManager.get(workflow_id)
        if not workflow:
            return jsonify({'error': 'Workflow not found'}), 404
        return jsonify(workflow)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/list', methods=['GET'])
def workflow_list():
    """List all workflows"""
    try:
        workflows = WorkflowManager.list_all()
        return jsonify({'list': workflows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/<workflow_id>', methods=['DELETE'])
def workflow_delete(workflow_id):
    """Delete a workflow"""
    try:
        success = WorkflowManager.delete(workflow_id)
        if not success:
            return jsonify({'error': 'Workflow not found'}), 404
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# endregion


# region Node Execution APIs

@app.route('/api/workflow/node/run', methods=['POST'])
def workflow_node_run():
    """Run a single node"""
    try:
        data = request.json
        node_type = data.get('type')
        config = data.get('config', {})
        input_data = data.get('input', {})
        
        if not node_type:
            return jsonify({'error': 'type is required'}), 400
        
        # Executors are now synchronous — call directly, no asyncio/threading needed
        output = ExecutorManager.run_node(node_type, config, input_data)
        return jsonify({'output': output})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# endregion


# region Workflow Execution APIs

@app.route('/api/workflow/run', methods=['POST'])
def workflow_run():
    """Run a workflow"""
    try:
        data = request.json
        workflow_id = data.get('workflowId')
        
        if not workflow_id:
            return jsonify({'error': 'workflowId is required'}), 400
        
        # Get workflow
        workflow = WorkflowManager.get(workflow_id)
        if not workflow:
            return jsonify({'error': 'Workflow not found'}), 404
        
        workflow_json = workflow.get('json')
        
        # Run workflow in background thread
        task_id = str(uuid.uuid4())
        
        def run_workflow():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                WorkflowRuntime.run(workflow_json, task_id)
            )
            loop.close()
        
        thread = threading.Thread(target=run_workflow)
        thread.start()
        
        return jsonify({'taskId': task_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/run/<task_id>/status', methods=['GET'])
def workflow_run_status(task_id):
    """Get workflow execution status"""
    try:
        task = WorkflowRuntime.get_task_status(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        return jsonify(task)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/run/<task_id>/cancel', methods=['POST'])
def workflow_run_cancel(task_id):
    """Cancel a running workflow"""
    try:
        success = WorkflowRuntime.cancel_task(task_id)
        if not success:
            return jsonify({'error': 'Task not found or not running'}), 404
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# endregion


# region Executor Management APIs

@app.route('/api/workflow/executors', methods=['GET'])
def workflow_executors():
    """List all registered node executors"""
    try:
        executors = ExecutorManager.list_executors()
        return jsonify({'executors': executors})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# endregion

