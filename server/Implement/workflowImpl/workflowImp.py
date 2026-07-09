import json
import os
import uuid
import asyncio
import logging
from datetime import datetime

WORKFLOW_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'workflow')

logger = logging.getLogger(__name__)


def _ensure_dir():
    os.makedirs(WORKFLOW_DATA_DIR, exist_ok=True)


def _workflow_path(workflow_id):
    return os.path.join(WORKFLOW_DATA_DIR, f"{workflow_id}.json")


def _get_socketio():
    """Lazily import socketio to avoid circular imports at module load time."""
    import g
    return getattr(g, 'socketio', None)


class WorkflowManager:
    @staticmethod
    def save(name, workflow_json, workflow_id=None, author=None, description=None):
        _ensure_dir()
        is_new = not workflow_id
        if not workflow_id:
            workflow_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        existing = None
        if not is_new:
            existing = WorkflowManager.get(workflow_id)

        record = {
            'id': workflow_id,
            'name': name,
            'json': workflow_json,
            'author': author or (existing.get('author', '') if existing else ''),
            'description': description or (existing.get('description', '') if existing else ''),
            'createdAt': existing.get('createdAt', now) if existing else now,
            'updatedAt': now,
        }
        with open(_workflow_path(workflow_id), 'w') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        return {'id': workflow_id, 'name': name}

    @staticmethod
    def get(workflow_id):
        path = _workflow_path(workflow_id)
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    @staticmethod
    def list_all():
        _ensure_dir()
        result = []
        for fname in os.listdir(WORKFLOW_DATA_DIR):
            if fname.endswith('.json'):
                with open(os.path.join(WORKFLOW_DATA_DIR, fname)) as f:
                    data = json.load(f)
                    result.append({
                        'id': data.get('id'),
                        'name': data.get('name'),
                        'author': data.get('author', ''),
                        'description': data.get('description', ''),
                        'createdAt': data.get('createdAt', ''),
                        'updatedAt': data.get('updatedAt', ''),
                    })
        result.sort(key=lambda x: x.get('updatedAt', ''), reverse=True)
        return result

    @staticmethod
    def delete(workflow_id):
        path = _workflow_path(workflow_id)
        if not os.path.exists(path):
            return False
        os.remove(path)
        return True


class WorkflowRuntime:
    """DAG-based workflow execution runtime with Socket.IO real-time push.

    Events emitted to the client room (task_id):
      - workflow:node_update  { taskId, nodeId, status, output }
      - workflow:done         { taskId, status, error }
    """

    _tasks: dict = {}

    @classmethod
    def _emit(cls, event: str, data: dict, room: str):
        """Thread-safe socketio emit."""
        sio = _get_socketio()
        if sio:
            try:
                sio.emit(event, data, room=room)
            except Exception as exc:
                logger.warning("[WorkflowRuntime._emit] Failed to emit %r to room %r: %s", event, room, exc)
        else:
            logger.debug("[WorkflowRuntime._emit] socketio not available, skip emit %r", event)

    @classmethod
    async def run(cls, workflow_json, task_id):
        from Implement.workflowImpl.nodeExecutor import ExecutorManager

        logger.info("[WorkflowRuntime.run] Starting: task_id=%r", task_id)

        nodes = workflow_json.get('nodes', [])
        edges = workflow_json.get('edges', [])

        logger.info("[WorkflowRuntime.run] task_id=%r, nodes=%d, edges=%d",
                    task_id, len(nodes), len(edges))

        if not nodes:
            logger.warning("[WorkflowRuntime.run] task_id=%r: no nodes found, finishing immediately", task_id)
            cls._tasks[task_id] = {'status': 'success', 'nodes': {}, 'result': {}}
            cls._emit('workflow:done', {'taskId': task_id, 'status': 'success', 'error': None}, room=task_id)
            return

        # ── Build adjacency structures ──────────────────────────────────────
        node_map = {n['id']: n for n in nodes}
        adj: dict = {n['id']: [] for n in nodes}
        predecessors: dict = {n['id']: [] for n in nodes}
        in_degree: dict = {n['id']: 0 for n in nodes}
        edges_by_target: dict = {n['id']: [] for n in nodes}

        for edge in edges:
            src = edge.get('source') or edge.get('sourceNodeID')
            tgt = edge.get('target') or edge.get('targetNodeID')
            if src in node_map and tgt in node_map:
                adj[src].append(tgt)
                predecessors[tgt].append(src)
                in_degree[tgt] += 1
                edges_by_target[tgt].append(edge)

        # ── Cycle detection ─────────────────────────────────────────────────
        from collections import deque
        topo_queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        topo_order = []
        topo_in_degree = dict(in_degree)
        while topo_queue:
            nid = topo_queue.popleft()
            topo_order.append(nid)
            for neighbor in adj[nid]:
                topo_in_degree[neighbor] -= 1
                if topo_in_degree[neighbor] == 0:
                    topo_queue.append(neighbor)

        if len(topo_order) != len(nodes):
            error_msg = "Workflow contains a cycle"
            logger.error("[WorkflowRuntime.run] task_id=%r: %s", task_id, error_msg)
            cls._tasks[task_id] = {
                'status': 'error', 'nodes': {n['id']: 'idle' for n in nodes},
                'result': None, 'error': error_msg,
            }
            cls._emit('workflow:done', {'taskId': task_id, 'status': 'error', 'error': error_msg}, room=task_id)
            raise ValueError(error_msg)

        root_nodes = [nid for nid, deg in in_degree.items() if deg == 0]
        logger.info("[WorkflowRuntime.run] task_id=%r, root_nodes=%s", task_id, root_nodes)

        # ── Initialize task state ────────────────────────────────────────────
        cls._tasks[task_id] = {
            'status': 'processing',
            'nodes': {nid: 'idle' for nid in node_map},
            'result': None,
            'error': None,
        }

        context: dict = {}
        context_lock = asyncio.Lock()
        node_done: dict = {nid: asyncio.Event() for nid in node_map}

        # ── Node executor coroutine ──────────────────────────────────────────
        async def execute_node(nid: str):
            node = node_map[nid]
            node_type = node.get('type', '')
            preds = predecessors[nid]

            if preds:
                logger.info("[WorkflowRuntime] task_id=%r, node=%r: waiting for predecessors %s",
                            task_id, nid, preds)
                await asyncio.gather(*[node_done[p].wait() for p in preds])
                logger.info("[WorkflowRuntime] task_id=%r, node=%r: all predecessors done", task_id, nid)

            # Check upstream errors
            async with context_lock:
                upstream_errors = [
                    f"{p}: {context[p].get('error')}"
                    for p in preds
                    if isinstance(context.get(p), dict) and context[p].get('error')
                ]
            if upstream_errors:
                error_msg = f"Upstream node(s) failed: {'; '.join(upstream_errors)}"
                logger.warning("[WorkflowRuntime] task_id=%r, node=%r: skipping due to upstream errors",
                               task_id, nid)
                async with context_lock:
                    context[nid] = {'error': error_msg}
                cls._tasks[task_id]['nodes'][nid] = 'error'
                cls._emit('workflow:node_update', {
                    'taskId': task_id, 'nodeId': nid, 'status': 'error', 'output': {'error': error_msg}
                }, room=task_id)
                node_done[nid].set()
                return

            # Assemble input_data via port mapping
            async with context_lock:
                input_data: dict = {}
                for edge in edges_by_target[nid]:
                    src = edge.get('source') or edge.get('sourceNodeID')
                    src_output = context.get(src, {})
                    target_handle = edge.get('targetHandle')
                    source_handle = edge.get('sourceHandle')
                    if target_handle and source_handle and source_handle in src_output:
                        input_data[target_handle] = src_output[source_handle]
                    elif target_handle:
                        input_data.update(src_output)
                    else:
                        input_data.update(src_output)

            logger.info("[WorkflowRuntime] task_id=%r, node=%r (type=%r): executing, input_keys=%s",
                        task_id, nid, node_type, list(input_data.keys()))

            # Push "running" status
            cls._tasks[task_id]['nodes'][nid] = 'processing'
            cls._emit('workflow:node_update', {
                'taskId': task_id, 'nodeId': nid, 'status': 'processing', 'output': None
            }, room=task_id)

            try:
                output = ExecutorManager.run_node(node_type, node.get('data', {}), input_data)
                async with context_lock:
                    context[nid] = output

                if isinstance(output, dict) and output.get('error'):
                    logger.warning("[WorkflowRuntime] task_id=%r, node=%r: executor error: %s",
                                   task_id, nid, output['error'])
                    cls._tasks[task_id]['nodes'][nid] = 'error'
                    cls._emit('workflow:node_update', {
                        'taskId': task_id, 'nodeId': nid, 'status': 'error', 'output': output
                    }, room=task_id)
                else:
                    logger.info("[WorkflowRuntime] task_id=%r, node=%r: success, output_keys=%s",
                                task_id, nid, list(output.keys()) if isinstance(output, dict) else type(output).__name__)
                    cls._tasks[task_id]['nodes'][nid] = 'success'
                    cls._emit('workflow:node_update', {
                        'taskId': task_id, 'nodeId': nid, 'status': 'success', 'output': output
                    }, room=task_id)

            except Exception as exc:
                logger.exception("[WorkflowRuntime] task_id=%r, node=%r: exception: %s", task_id, nid, exc)
                async with context_lock:
                    context[nid] = {'error': str(exc)}
                cls._tasks[task_id]['nodes'][nid] = 'error'
                cls._emit('workflow:node_update', {
                    'taskId': task_id, 'nodeId': nid, 'status': 'error', 'output': {'error': str(exc)}
                }, room=task_id)
            finally:
                node_done[nid].set()

        # ── Launch all coroutines concurrently ───────────────────────────────
        logger.info("[WorkflowRuntime.run] task_id=%r: launching %d node coroutines", task_id, len(nodes))
        await asyncio.gather(*[execute_node(nid) for nid in node_map])

        # ── Finalize ─────────────────────────────────────────────────────────
        failed_nodes = [nid for nid, st in cls._tasks[task_id]['nodes'].items() if st == 'error']
        if failed_nodes:
            cls._tasks[task_id]['status'] = 'error'
            cls._tasks[task_id]['error'] = f"Node(s) failed: {failed_nodes}"
            logger.warning("[WorkflowRuntime.run] task_id=%r: finished with errors: %s", task_id, failed_nodes)
            cls._emit('workflow:done', {
                'taskId': task_id, 'status': 'error', 'error': cls._tasks[task_id]['error']
            }, room=task_id)
        else:
            cls._tasks[task_id]['status'] = 'success'
            logger.info("[WorkflowRuntime.run] task_id=%r: finished successfully", task_id)
            cls._emit('workflow:done', {'taskId': task_id, 'status': 'success', 'error': None}, room=task_id)

        cls._tasks[task_id]['result'] = context

    @classmethod
    def get_task_status(cls, task_id):
        return cls._tasks.get(task_id)

    @classmethod
    def cancel_task(cls, task_id):
        task = cls._tasks.get(task_id)
        if task and task.get('status') == 'processing':
            task['status'] = 'canceled'
            logger.info("[WorkflowRuntime.cancel_task] task_id=%r canceled", task_id)
            cls._emit('workflow:done', {'taskId': task_id, 'status': 'canceled', 'error': None}, room=task_id)
            return True
        logger.warning("[WorkflowRuntime.cancel_task] task_id=%r not found or not running", task_id)
        return False
