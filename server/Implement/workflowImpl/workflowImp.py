import json
import os
import re
import asyncio
import logging
from datetime import datetime, timezone

WORKFLOW_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'workflow')

logger = logging.getLogger(__name__)


def _ensure_dir():
    os.makedirs(WORKFLOW_DATA_DIR, exist_ok=True)


def _sanitize_name(name: str) -> str:
    """Convert a workflow name to a safe filename (keep alphanumeric, CJK, hyphen, underscore)."""
    # Replace spaces and common separators with underscore
    s = name.strip().replace(' ', '_').replace('/', '_').replace('\\', '_')
    # Remove characters that are unsafe in filenames
    s = re.sub(r'[<>:"|?*]', '', s)
    # If empty after sanitizing, fallback
    return s or 'untitled'


def _workflow_path(workflow_id: str) -> str:
    return os.path.join(WORKFLOW_DATA_DIR, f"{workflow_id}.json")


def _get_socketio():
    """Lazily import socketio to avoid circular imports at module load time."""
    import g
    return getattr(g, 'socketio', None)


class WorkflowManager:
    @staticmethod
    def save(name, workflow_json, workflow_id=None, author=None, description=None):
        """Save or update a workflow.

        The workflow is stored as <name>.json where name is sanitized.
        If workflow_id is provided and differs from the sanitized name, the old file
        is migrated (renamed) to the new name-based path.
        """
        _ensure_dir()
        name_id = _sanitize_name(name)
        now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        # Load existing record — prefer by name_id, fallback to old UUID-based id
        existing = WorkflowManager.get(name_id) or (WorkflowManager.get(workflow_id) if workflow_id else None)

        # Migrate old UUID file if needed
        if workflow_id and workflow_id != name_id:
            old_path = _workflow_path(workflow_id)
            if os.path.exists(old_path):
                os.remove(old_path)
                logger.info("[WorkflowManager.save] Migrated %r → %r", workflow_id, name_id)

        record = {
            'id': name_id,
            'name': name,
            'json': workflow_json,
            'author': author or (existing.get('author', '') if existing else ''),
            'description': description or (existing.get('description', '') if existing else ''),
            'createdAt': existing.get('createdAt', now) if existing else now,
            'updatedAt': now,
        }
        with open(_workflow_path(name_id), 'w') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        return {'id': name_id, 'name': name}

    @staticmethod
    def get(workflow_id):
        if not workflow_id:
            return None
        path = _workflow_path(workflow_id)
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        # Fallback: scan by name field (handles legacy UUID-based IDs in URLs)
        _ensure_dir()
        for fname in os.listdir(WORKFLOW_DATA_DIR):
            if not fname.endswith('.json'):
                continue
            fp = os.path.join(WORKFLOW_DATA_DIR, fname)
            try:
                with open(fp) as f:
                    data = json.load(f)
                if data.get('id') == workflow_id or data.get('name') == workflow_id:
                    return data
            except Exception:
                pass
        return None

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
        # Try direct path first
        path = _workflow_path(workflow_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        # Fallback: find by name
        record = WorkflowManager.get(workflow_id)
        if record:
            p = _workflow_path(record['id'])
            if os.path.exists(p):
                os.remove(p)
                return True
        return False


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
    async def run(cls, workflow_json, task_id, start_node_id: str = None, node_data_overrides: dict = None):
        """Run workflow (full graph or subgraph from start_node_id).

        Args:
            workflow_json:       Saved workflow JSON (nodes + edges).
            task_id:             Unique task identifier for this run.
            start_node_id:       If set, only execute this node and all its downstream nodes.
                                 Predecessors of start_node_id are NOT executed; their outputs
                                 are assumed to be already available in node_data_overrides.
            node_data_overrides: Per-node data dict overrides { nodeId: { fieldKey: value, ... } }.
                                 Used to inject the latest field values from the frontend without
                                 requiring a save first.
        """
        from Implement.workflowImpl.nodeExecutor import ExecutorManager

        logger.info("[WorkflowRuntime.run] Starting: task_id=%r, start_node_id=%r", task_id, start_node_id)

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

        # ── Cycle detection via full-graph topological sort ─────────────────
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

        # ── Determine which nodes to execute ─────────────────────────────────
        # Full graph: all nodes in topo order.
        # Subgraph (start_node_id set): start_node + all reachable downstream nodes (BFS).
        if start_node_id and start_node_id in node_map:
            # BFS to find all nodes reachable from start_node_id
            subgraph_nodes = set()
            bfs_queue = deque([start_node_id])
            while bfs_queue:
                nid = bfs_queue.popleft()
                if nid in subgraph_nodes:
                    continue
                subgraph_nodes.add(nid)
                for downstream in adj[nid]:
                    bfs_queue.append(downstream)
            # Keep topological order but only for subgraph nodes
            exec_nodes = [nid for nid in topo_order if nid in subgraph_nodes]
            logger.info("[WorkflowRuntime.run] task_id=%r: subgraph from %r, exec_nodes=%s",
                        task_id, start_node_id, exec_nodes)
        elif start_node_id and start_node_id not in node_map:
            # start_node_id was specified but not found in saved workflow — likely unsaved node
            error_msg = f"Start node '{start_node_id}' not found in workflow (workflow may need to be saved first)"
            logger.error("[WorkflowRuntime.run] task_id=%r: %s", task_id, error_msg)
            cls._tasks[task_id] = {
                'status': 'error', 'nodes': {}, 'result': None, 'error': error_msg,
            }
            # Emit error for the start node so the frontend can reset its status
            cls._emit('workflow:node_update', {
                'taskId': task_id, 'nodeId': start_node_id, 'status': 'error',
                'output': {'error': error_msg}
            }, room=task_id)
            cls._emit('workflow:done', {'taskId': task_id, 'status': 'error', 'error': error_msg}, room=task_id)
            return
        else:
            exec_nodes = list(topo_order)
            logger.info("[WorkflowRuntime.run] task_id=%r: full graph, exec_nodes=%s", task_id, exec_nodes)

        # ── Initialize task state ────────────────────────────────────────────
        cls._tasks[task_id] = {
            'status': 'processing',
            'nodes': {nid: 'idle' for nid in node_map},
            'result': None,
            'error': None,
        }

        # Pre-fill context with upstream outputs passed from the frontend (node_data_overrides).
        # For subgraph runs: predecessors of start_node are not executed; we put placeholder
        # entries in context so that edge port mapping in execute_node can find their outputs.
        context: dict = {}
        if node_data_overrides:
            for nid, override_data in node_data_overrides.items():
                if nid not in [n for n in exec_nodes]:
                    # This is an upstream node not in exec set — store its output in context
                    # so downstream port mapping can reference it.
                    context[nid] = override_data
                    logger.debug("[WorkflowRuntime.run] task_id=%r: pre-filled context for upstream node %r", task_id, nid)

        context_lock = asyncio.Lock()

        # asyncio.Event per node — only create for nodes we actually execute
        node_done: dict = {nid: asyncio.Event() for nid in node_map}

        # Pre-mark predecessors of exec_nodes that are NOT in exec_nodes as already done,
        # so execute_node doesn't wait forever for them.
        exec_set = set(exec_nodes)
        for nid in node_map:
            if nid not in exec_set:
                node_done[nid].set()

        # ── Node executor coroutine ──────────────────────────────────────────
        async def execute_node(nid: str):
            node = node_map[nid]
            node_type = node.get('type', '')
            preds = predecessors[nid]

            # Wait for predecessors (already-done predecessors return immediately)
            if preds:
                logger.info("[WorkflowRuntime] task_id=%r, node=%r: waiting for predecessors %s",
                            task_id, nid, preds)
                await asyncio.gather(*[node_done[p].wait() for p in preds])
                logger.info("[WorkflowRuntime] task_id=%r, node=%r: all predecessors done", task_id, nid)

            # Check upstream errors (only for predecessors that were in exec set)
            async with context_lock:
                upstream_errors = [
                    f"{p}: {context[p].get('error')}"
                    for p in preds
                    if p in exec_set and isinstance(context.get(p), dict) and context[p].get('error')
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

            # Merge node data with any frontend overrides
            node_data = dict(node.get('data', {}))
            if node_data_overrides and nid in node_data_overrides:
                node_data.update(node_data_overrides[nid])

            logger.info("[WorkflowRuntime] task_id=%r, node=%r (type=%r): executing, input_keys=%s",
                        task_id, nid, node_type, list(input_data.keys()))

            # Push "running" status
            cls._tasks[task_id]['nodes'][nid] = 'processing'
            cls._emit('workflow:node_update', {
                'taskId': task_id, 'nodeId': nid, 'status': 'processing', 'output': None
            }, room=task_id)

            try:
                output = ExecutorManager.run_node(node_type, node_data, input_data)
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

        # ── Launch coroutines for exec_nodes only ────────────────────────────
        logger.info("[WorkflowRuntime.run] task_id=%r: launching %d node coroutines (of %d total)",
                    task_id, len(exec_nodes), len(node_map))
        await asyncio.gather(*[execute_node(nid) for nid in exec_nodes])

        # ── Finalize (only consider executed nodes for error check) ──────────
        failed_nodes = [nid for nid in exec_nodes if cls._tasks[task_id]['nodes'].get(nid) == 'error']
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
