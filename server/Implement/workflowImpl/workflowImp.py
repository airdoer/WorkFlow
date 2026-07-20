import json
import os
import re
import shutil
import asyncio
import logging
from datetime import datetime, timezone

WORKFLOW_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'workflow')
WORKFLOW_TRASH_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'workflow_trash')

# Threshold: node _runOutput larger than this (bytes) gets archived to disk
_ARCHIVE_THRESHOLD = 10240  # 10 KB
# Keys within _runOutput that are always archived (large file content)
_ARCHIVE_KEYS = frozenset({'fileContent'})

logger = logging.getLogger(__name__)

# Internal meta keys that should NOT be passed to downstream nodes via fallback update.
_META_KEYS = frozenset({'__runtime_type__', '__value__'})


def _ensure_dir():
    os.makedirs(WORKFLOW_DATA_DIR, exist_ok=True)


def _ensure_trash_dir():
    os.makedirs(WORKFLOW_TRASH_DIR, exist_ok=True)


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


def _trash_path(workflow_id: str) -> str:
    return os.path.join(WORKFLOW_TRASH_DIR, f"{workflow_id}.json")


def _get_socketio():
    """Lazily import socketio to avoid circular imports at module load time."""
    import g
    return getattr(g, 'socketio', None)


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def _archive_dir(name_id: str) -> str:
    """Return the archive directory path for a workflow."""
    return os.path.join(WORKFLOW_DATA_DIR, f"{name_id}_archive")


def _history_path(name_id: str) -> str:
    """Return the execution history file path for a workflow."""
    d = _archive_dir(name_id)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, 'history.json')


def _archive_node_path(name_id: str, node_id: str) -> str:
    """Return the archive file path for a specific node's _runOutput."""
    d = _archive_dir(name_id)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, node_id)


def _archive_strip_outputs(name_id: str, nodes: list) -> list:
    """Strip large _runOutput from nodes, writing content to archive dir.
    
    Returns a new nodes list with large outputs replaced by _archiveRef markers.
    """
    for node in nodes:
        data = node.get('data', {})
        output = data.get('_runOutput')
        if output is None:
            continue
        # Case 1: output is a dict containing fileContent or other huge keys
        if isinstance(output, dict):
            has_archive_key = bool(_ARCHIVE_KEYS & output.keys())
            output_size = len(json.dumps(output, ensure_ascii=False))
            if has_archive_key or output_size > _ARCHIVE_THRESHOLD:
                # Write full output to archive
                archive_path = _archive_node_path(name_id, node.get('id', 'unknown'))
                with open(archive_path, 'w', encoding='utf-8') as f:
                    json.dump(output, f, ensure_ascii=False)
                # Replace with reference marker
                data['_runOutput'] = {'_archiveRef': node.get('id', 'unknown')}
                # Preserve status hint
                if '_runStatus' in data and '_runStatusHint' not in data:
                    data['_runStatusHint'] = data['_runStatus']
                continue
        # Case 2: output is a string/list larger than threshold
        if isinstance(output, (str, list)):
            output_size = len(json.dumps(output, ensure_ascii=False))
            if output_size > _ARCHIVE_THRESHOLD:
                archive_path = _archive_node_path(name_id, node.get('id', 'unknown'))
                with open(archive_path, 'w', encoding='utf-8') as f:
                    json.dump(output, f, ensure_ascii=False)
                data['_runOutput'] = {'_archiveRef': node.get('id', 'unknown')}
    return nodes


def _archive_restore_outputs(name_id: str, nodes: list) -> list:
    """Restore archived _runOutput from disk for nodes that have _archiveRef markers."""
    archive_d = _archive_dir(name_id)
    if not os.path.isdir(archive_d):
        return nodes
    for node in nodes:
        data = node.get('data', {})
        output = data.get('_runOutput')
        if isinstance(output, dict) and '_archiveRef' in output:
            ref_id = output['_archiveRef']
            archive_path = os.path.join(archive_d, ref_id)
            if os.path.exists(archive_path):
                try:
                    with open(archive_path, 'r', encoding='utf-8') as f:
                        data['_runOutput'] = json.load(f)
                except Exception:
                    logger.warning("[archive_restore] Failed to read archive for node %r", ref_id)
            else:
                logger.warning("[archive_restore] Archive file not found for node %r", ref_id)
    return nodes


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
        now = _now_utc()

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

        # ── Archive large _runOutput from node data ──────────────────
        wf_json = record.get('json', {})
        if isinstance(wf_json, dict) and 'nodes' in wf_json:
            record['json']['nodes'] = _archive_strip_outputs(name_id, wf_json['nodes'])

        with open(_workflow_path(name_id), 'w') as f:
            json.dump(record, f, ensure_ascii=False)
        return {'id': name_id, 'name': name}

    @staticmethod
    def get(workflow_id):
        if not workflow_id:
            return None
        path = _workflow_path(workflow_id)
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            # ── Restore archived _runOutput from disk ───────────────
            wf_json = data.get('json', {})
            if isinstance(wf_json, dict) and 'nodes' in wf_json:
                data['json']['nodes'] = _archive_restore_outputs(workflow_id, wf_json['nodes'])
            return data
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
                    # Restore archived _runOutput
                    wf_json = data.get('json', {})
                    if isinstance(wf_json, dict) and 'nodes' in wf_json:
                        data['json']['nodes'] = _archive_restore_outputs(data.get('id', workflow_id), wf_json['nodes'])
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
    def delete(workflow_id) -> bool:
        """Move workflow to trash instead of permanently deleting."""
        _ensure_trash_dir()

        # Find the record first
        record = WorkflowManager.get(workflow_id)
        if not record:
            # Try direct path
            path = _workflow_path(workflow_id)
            if not os.path.exists(path):
                return False
            with open(path) as f:
                record = json.load(f)

        # Add deletedAt timestamp and move to trash
        record['deletedAt'] = _now_utc()
        trash_file = _trash_path(record['id'])
        with open(trash_file, 'w') as f:
            json.dump(record, f, ensure_ascii=False)

        # Remove from active directory
        src = _workflow_path(record['id'])
        if os.path.exists(src):
            os.remove(src)
            # Also remove the archive directory if it exists
            archive_d = _archive_dir(record['id'])
            if os.path.isdir(archive_d):
                shutil.rmtree(archive_d, ignore_errors=True)
                logger.info("[WorkflowManager.delete] Removed archive dir: %r", archive_d)
            logger.info("[WorkflowManager.delete] Moved to trash: %r", record['id'])
            return True

        return False

    # ── Trash operations ─────────────────────────────────────────

    @staticmethod
    def list_trash():
        """Return all workflows in the trash."""
        _ensure_trash_dir()
        result = []
        for fname in os.listdir(WORKFLOW_TRASH_DIR):
            if fname.endswith('.json'):
                fp = os.path.join(WORKFLOW_TRASH_DIR, fname)
                try:
                    with open(fp) as f:
                        data = json.load(f)
                    result.append({
                        'id': data.get('id'),
                        'name': data.get('name'),
                        'author': data.get('author', ''),
                        'deletedAt': data.get('deletedAt', ''),
                        'updatedAt': data.get('updatedAt', ''),
                    })
                except Exception:
                    pass
        result.sort(key=lambda x: x.get('deletedAt', ''), reverse=True)
        return result

    @staticmethod
    def restore(workflow_id) -> bool:
        """Restore a workflow from trash back to active directory."""
        _ensure_dir()
        trash_file = _trash_path(workflow_id)
        if not os.path.exists(trash_file):
            return False
        with open(trash_file) as f:
            record = json.load(f)

        # Remove deletedAt and restore
        record.pop('deletedAt', None)
        active_file = _workflow_path(record['id'])
        with open(active_file, 'w') as f:
            json.dump(record, f, ensure_ascii=False)

        os.remove(trash_file)
        logger.info("[WorkflowManager.restore] Restored from trash: %r", workflow_id)
        return True

    @staticmethod
    def purge(workflow_id) -> bool:
        """Permanently delete a workflow from trash."""
        trash_file = _trash_path(workflow_id)
        if os.path.exists(trash_file):
            os.remove(trash_file)
            logger.info("[WorkflowManager.purge] Permanently deleted: %r", workflow_id)
            return True
        return False

    @staticmethod
    def duplicate(source_id: str, new_name: str) -> dict | None:
        """Duplicate an existing workflow with a new name."""
        source = WorkflowManager.get(source_id)
        if not source:
            return None
        import copy
        new_json = copy.deepcopy(source.get('json', {}))
        result = WorkflowManager.save(
            name=new_name,
            workflow_json=new_json,
            author=source.get('author', ''),
            description=source.get('description', ''),
        )
        logger.info("[WorkflowManager.duplicate] %r → %r", source_id, result.get('id'))
        return result

    # ── Execution History ──────────────────────────────────────────

    MAX_HISTORY_RECORDS = 100

    @staticmethod
    def add_history(workflow_id, record):
        """Append an execution history record. Keeps at most MAX_HISTORY_RECORDS."""
        path = _history_path(workflow_id)
        data = {"records": []}
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                data = {"records": []}
        records = data.get('records', [])
        records.append(record)
        # FIFO: keep only the latest MAX_HISTORY_RECORDS
        if len(records) > WorkflowManager.MAX_HISTORY_RECORDS:
            records = records[-WorkflowManager.MAX_HISTORY_RECORDS:]
        data['records'] = records
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def get_history(workflow_id):
        """Get execution history for a workflow."""
        path = _history_path(workflow_id)
        if not os.path.exists(path):
            return {"records": []}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"records": []}

    @staticmethod
    def get_recent_history(username=None, limit=50):
        """Get recent execution history across all workflows.
        If username is provided, only return workflows authored by that user."""
        _ensure_dir()
        all_records = []
        for fname in os.listdir(WORKFLOW_DATA_DIR):
            if not fname.endswith('.json'):
                continue
            fp = os.path.join(WORKFLOW_DATA_DIR, fname)
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    wf = json.load(f)
            except Exception:
                continue
            wf_id = wf.get('id', '')
            wf_name = wf.get('name', '')
            wf_author = wf.get('author', '')
            if username and wf_author != username:
                continue
            hist_path = _history_path(wf_id)
            if not os.path.exists(hist_path):
                continue
            try:
                with open(hist_path, 'r', encoding='utf-8') as f:
                    hist = json.load(f)
            except Exception:
                continue
            for rec in hist.get('records', []):
                rec_copy = dict(rec)
                rec_copy['workflowId'] = wf_id
                rec_copy['workflowName'] = wf_name
                rec_copy['workflowAuthor'] = wf_author
                all_records.append(rec_copy)
        # Sort by startedAt descending
        all_records.sort(key=lambda x: x.get('startedAt', ''), reverse=True)
        return all_records[:limit]

    @staticmethod
    def list_by_author(author):
        """List workflows filtered by author."""
        _ensure_dir()
        result = []
        for fname in os.listdir(WORKFLOW_DATA_DIR):
            if not fname.endswith('.json'):
                continue
            with open(os.path.join(WORKFLOW_DATA_DIR, fname), 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get('author', '') == author:
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

            # Check upstream errors — if any predecessor failed, skip this node silently
            async with context_lock:
                upstream_failed = any(
                    p in exec_set and isinstance(context.get(p), dict) and context[p].get('error')
                    for p in preds
                )
            if upstream_failed:
                logger.info("[WorkflowRuntime] task_id=%r, node=%r: skipped (upstream node failed)",
                            task_id, nid)
                async with context_lock:
                    context[nid] = {'error': '__skip__', 'skipped': True}
                cls._tasks[task_id]['nodes'][nid] = 'skipped'
                cls._emit('workflow:node_update', {
                    'taskId': task_id, 'nodeId': nid, 'status': 'skipped',
                    'output': {'skipped': True}
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
                        # Precise mapping: source_handle key exists in output → direct assign
                        input_data[target_handle] = src_output[source_handle]
                        # Propagate file metadata alongside file content so downstream
                        # renderers (Excel, Lua, etc.) can use localPath / fileType.
                        if source_handle == 'fileContent':
                            for meta_key in ('localPath', 'fileType', 'filePath'):
                                if meta_key in src_output:
                                    input_data.setdefault(meta_key, src_output[meta_key])
                    elif target_handle and source_handle:
                        # source_handle NOT in src_output → try __value__ fallback
                        # This handles cases where port key (e.g. 'result') differs
                        # from executor output key (e.g. 'value', 'rows', etc.)
                        if '__value__' in src_output:
                            input_data[target_handle] = src_output['__value__']
                        elif 'localPath' in src_output:
                            # File-reference node (P4File, etc.) whose port key was removed
                            # from output for storage optimization. Pass the entire output
                            # dict so downstream nodes (Diff, etc.) can read the file via
                            # localPath. For Excel and other nodes expecting a string path,
                            # their executors should extract localPath from the dict.
                            input_data[target_handle] = src_output
                        else:
                            # Last resort: merge all business keys by name
                            for k, v in src_output.items():
                                if k not in _META_KEYS:
                                    input_data[k] = v
                    elif target_handle:
                        # No source_handle: assign entire output dict to target handle
                        # This preserves the value as a single object rather than
                        # flattening keys (which can cause collisions).
                        input_data[target_handle] = src_output
                    else:
                        # No handle info at all: fall back to key-level merge
                        for k, v in src_output.items():
                            if k not in _META_KEYS:
                                input_data[k] = v

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
                    # Strip internal meta keys before sending to frontend
                    clean_output = {k: v for k, v in output.items() if k not in _META_KEYS}
                    cls._emit('workflow:node_update', {
                        'taskId': task_id, 'nodeId': nid, 'status': 'error', 'output': clean_output or output
                    }, room=task_id)

                elif isinstance(output, dict) and output.get('_sealPolling'):
                    # ── Seal 异步轮询模式 ──────────────────────────────────
                    # 任务已创建并启动，需要后台轮询 SOPS 状态
                    # 协程会 await 轮询完成事件，确保 asyncio.gather 正确等待
                    seal_task_id = output.get('_sealTaskId') or output.get('taskId')
                    logger.info("[WorkflowRuntime] task_id=%r, node=%r: Seal polling started, "
                                "seal_task_id=%s", task_id, nid, seal_task_id)

                    # 保存 event loop 引用，后台线程需要用它唤醒协程
                    loop = asyncio.get_running_loop()

                    # 创建轮询完成事件，协程会 await 它
                    seal_poll_done = asyncio.Event()

                    # 推送中间状态（创建成功，但执行中）
                    clean_output = {k: v for k, v in output.items()
                                    if k not in _META_KEYS and k != '_sealPolling' and k != '_sealTaskId'}
                    clean_output['executionSuccess'] = None  # 尚未完成
                    clean_output['_pollingStatus'] = 'polling'  # 告知前端正在轮询
                    cls._emit('workflow:node_update', {
                        'taskId': task_id, 'nodeId': nid, 'status': 'processing',
                        'output': clean_output
                    }, room=task_id)

                    # 启动后台轮询线程
                    import threading
                    poll_thread = threading.Thread(
                        target=cls._seal_poll_and_finish,
                        daemon=True,
                        name=f"seal-poll-{seal_task_id}",
                        args=(task_id, nid, seal_task_id, context, context_lock,
                              node_done, loop, seal_poll_done)
                    )
                    poll_thread.start()

                    # ★ 协程等待轮询完成 — 确保 asyncio.gather 不会提前结束
                    await seal_poll_done.wait()

                    # 轮询完成后，context[nid] 已被后台线程更新
                    final_output = context.get(nid, {})
                    final_status = cls._tasks[task_id]['nodes'].get(nid, 'error')

                    # 推送最终状态
                    clean_final = {k: v for k, v in final_output.items()
                                   if k not in _META_KEYS and k != '_sealPolling' and k != '_sealTaskId'}
                    cls._emit('workflow:node_update', {
                        'taskId': task_id, 'nodeId': nid, 'status': final_status,
                        'output': clean_final
                    }, room=task_id)

                    logger.info("[WorkflowRuntime] task_id=%r, node=%r: Seal polling completed, "
                                "final_status=%s", task_id, nid, final_status)

                else:
                    logger.info("[WorkflowRuntime] task_id=%r, node=%r: success, output_keys=%s",
                                task_id, nid, list(output.keys()) if isinstance(output, dict) else type(output).__name__)
                    cls._tasks[task_id]['nodes'][nid] = 'success'
                    # Strip internal meta keys before sending to frontend
                    clean_output = {k: v for k, v in output.items() if k not in _META_KEYS} if isinstance(output, dict) else output
                    cls._emit('workflow:node_update', {
                        'taskId': task_id, 'nodeId': nid, 'status': 'success', 'output': clean_output
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

    # ── Seal 异步轮询 ─────────────────────────────────────────────────────────

    @classmethod
    def _seal_poll_and_finish(cls, wf_task_id: str, node_id: str, seal_task_id: str,
                               context: dict, context_lock, node_done: dict, loop,
                               seal_poll_done):
        """
        后台线程：轮询 SOPS 任务状态，完成后更新 context 和任务状态，
        然后通过 seal_poll_done 通知 execute_node 协程。

        参数:
            wf_task_id: 工作流 task_id（Socket.IO room）
            node_id: 工作流节点 ID
            seal_task_id: SOPS 任务 ID
            context: 工作流共享上下文
            context_lock: asyncio.Lock（主事件循环的锁）
            node_done: {node_id: asyncio.Event} 用于通知下游节点
            loop: 主事件循环引用（asyncio.AbstractEventLoop）
            seal_poll_done: asyncio.Event — 轮询完成后通知协程
        """
        from Implement.hotfixImpl.sealImp import SealClient
        client = SealClient()

        logger.info("[SealPoll] Started: wf_task=%s, node=%s, seal_task=%s",
                     wf_task_id, node_id, seal_task_id)

        # 轮询等待 SOPS 任务完成（每 60 秒，最多 30 分钟）
        result = client.wait_for_task_completion(
            seal_task_id, poll_interval=30, timeout=1800
        )

        logger.info("[SealPoll] Finished: seal_task=%s, completed=%s, state=%s, elapsed=%.1fs",
                     seal_task_id, result.get('completed'), result.get('state'), result.get('elapsed', 0))

        # 判断最终结果
        is_success = (result.get('completed') and result.get('state', '').upper() == 'FINISHED'
                      and not result.get('failed_nodes'))

        # 更新 context 中的 output
        node_output = context.get(node_id, {})
        if isinstance(node_output, dict):
            node_output['executionSuccess'] = is_success
            node_output.pop('_sealPolling', None)
            node_output.pop('_sealTaskId', None)
            node_output.pop('_pollingStatus', None)
            # 补充轮询结果信息
            node_output['sealState'] = result.get('state', 'UNKNOWN')
            node_output['sealElapsed'] = result.get('elapsed', 0)
            node_output['sealPollCount'] = result.get('poll_count', 0)
            if result.get('failed_nodes'):
                node_output['failedNodes'] = result.get('failed_nodes')
            if result.get('error'):
                node_output['sealError'] = result.get('error')

        # 更新工作流任务状态（供 finalize 阶段检查）
        if is_success:
            final_status = 'success'
        else:
            final_status = 'error'
            # 如果任务完成但非 FINISHED，设置错误信息
            if not node_output.get('error'):
                error_msg = result.get('error', '') or f"SOPS 任务终态: {result.get('state', 'UNKNOWN')}"
                node_output['error'] = error_msg

        cls._tasks[wf_task_id]['nodes'][node_id] = final_status

        logger.info("[SealPoll] Node %s final status: %s, executionSuccess=%s",
                     node_id, final_status, is_success)

        # 通知 execute_node 协程：轮询完成，可以继续了
        try:
            loop.call_soon_threadsafe(seal_poll_done.set)
        except Exception as e:
            logger.warning("[SealPoll] Failed to notify poll_done for %s: %s", node_id, e)
            # Fallback
            try:
                seal_poll_done.set()
            except Exception:
                pass

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
