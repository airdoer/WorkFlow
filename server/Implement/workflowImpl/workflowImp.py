import json
import os
import uuid
from datetime import datetime

WORKFLOW_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'workflow')


def _ensure_dir():
    os.makedirs(WORKFLOW_DATA_DIR, exist_ok=True)


def _workflow_path(workflow_id):
    return os.path.join(WORKFLOW_DATA_DIR, f"{workflow_id}.json")


class WorkflowManager:
    @staticmethod
    def save(name, workflow_json, workflow_id=None):
        _ensure_dir()
        if not workflow_id:
            workflow_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        record = {
            'id': workflow_id,
            'name': name,
            'json': workflow_json,
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
                        'updatedAt': data.get('updatedAt'),
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
    _tasks = {}

    @classmethod
    async def run(cls, workflow_json, task_id):
        from Implement.workflowImpl.nodeExecutor import ExecutorManager
        from collections import deque

        nodes = workflow_json.get('nodes', [])
        edges = workflow_json.get('edges', [])

        adj = {n['id']: [] for n in nodes}
        in_degree = {n['id']: 0 for n in nodes}
        node_map = {n['id']: n for n in nodes}

        for edge in edges:
            src = edge.get('sourceNodeID')
            tgt = edge.get('targetNodeID')
            if src in adj and tgt in in_degree:
                adj[src].append(tgt)
                in_degree[tgt] += 1

        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        order = []
        while queue:
            nid = queue.popleft()
            order.append(nid)
            for neighbor in adj[nid]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(nodes):
            raise ValueError("Workflow contains a cycle")

        cls._tasks[task_id] = {
            'status': 'processing',
            'nodes': {nid: 'idle' for nid in order},
            'result': None,
        }

        context = {}
        for nid in order:
            node = node_map[nid]
            cls._tasks[task_id]['nodes'][nid] = 'processing'

            input_edges = [e for e in edges if e.get('targetNodeID') == nid]
            input_data = {}
            for edge in input_edges:
                src_output = context.get(edge.get('sourceNodeID'), {})
                input_data.update(src_output)

            output = await ExecutorManager.run_node(node.get('type', ''), node.get('data', {}), input_data)
            context[nid] = output
            cls._tasks[task_id]['nodes'][nid] = 'success'

        cls._tasks[task_id]['status'] = 'success'
        cls._tasks[task_id]['result'] = context

    @classmethod
    def get_task_status(cls, task_id):
        return cls._tasks.get(task_id)

    @classmethod
    def cancel_task(cls, task_id):
        if task_id in cls._tasks:
            cls._tasks[task_id]['status'] = 'canceled'
            return True
        return False
