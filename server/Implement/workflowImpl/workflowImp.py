"""
Workflow CRUD and Runtime Implementation
"""
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import asyncio


# In-memory storage (for now, can be replaced with database later)
_workflows: Dict[str, Dict[str, Any]] = {}
_tasks: Dict[str, Dict[str, Any]] = {}


class WorkflowManager:
    """Manages workflow CRUD operations"""
    
    @staticmethod
    def save(name: str, workflow_json: Dict[str, Any], workflow_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Save or update a workflow
        
        Args:
            name: Workflow name
            workflow_json: Workflow JSON data
            workflow_id: Optional workflow ID (for updates)
            
        Returns:
            Workflow info with id and name
        """
        if workflow_id is None:
            workflow_id = str(uuid.uuid4())
        
        _workflows[workflow_id] = {
            "id": workflow_id,
            "name": name,
            "json": workflow_json,
            "created_at": datetime.now().isoformat() if workflow_id not in _workflows else _workflows[workflow_id].get("created_at"),
            "updated_at": datetime.now().isoformat()
        }
        
        return {"id": workflow_id, "name": name}
    
    @staticmethod
    def get(workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow by ID"""
        return _workflows.get(workflow_id)
    
    @staticmethod
    def list_all() -> List[Dict[str, Any]]:
        """List all workflows"""
        return [
            {
                "id": wf["id"],
                "name": wf["name"],
                "updatedAt": wf["updated_at"]
            }
            for wf in _workflows.values()
        ]
    
    @staticmethod
    def delete(workflow_id: str) -> bool:
        """Delete a workflow"""
        if workflow_id in _workflows:
            del _workflows[workflow_id]
            return True
        return False


class WorkflowRuntime:
    """Handles workflow execution"""
    
    @staticmethod
    async def run(workflow_json: Dict[str, Any], task_id: Optional[str] = None) -> str:
        """
        Run a workflow
        
        Args:
            workflow_json: Workflow JSON data
            task_id: Optional task ID
            
        Returns:
            Task ID for tracking execution
        """
        from .nodeExecutor import ExecutorManager
        
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        # Initialize task status
        _tasks[task_id] = {
            "id": task_id,
            "status": "running",
            "nodes": {},
            "result": None,
            "error": None,
            "started_at": datetime.now().isoformat()
        }
        
        # Parse workflow
        nodes = workflow_json.get("nodes", [])
        edges = workflow_json.get("edges", [])
        
        # Build DAG
        node_map = {node["id"]: node for node in nodes}
        execution_order = WorkflowRuntime._topological_sort(nodes, edges)
        
        # Context for storing node outputs
        context = {}
        
        try:
            # Execute nodes in order
            for node_id in execution_order:
                node = node_map[node_id]
                node_type = node.get("type")
                node_data = node.get("data", {})
                
                # Mark node as started
                _tasks[task_id]["nodes"][node_id] = "running"
                
                # Collect inputs from upstream nodes
                input_data = {}
                for edge in edges:
                    if edge.get("targetNodeID") == node_id:
                        source_id = edge.get("sourceNodeID")
                        if source_id in context:
                            input_data[source_id] = context[source_id]
                
                # Execute node
                output = await ExecutorManager.run_node(node_type, node_data, input_data)
                context[node_id] = output
                
                # Mark node as completed
                _tasks[task_id]["nodes"][node_id] = "completed"
            
            # Mark workflow as completed
            _tasks[task_id]["status"] = "completed"
            _tasks[task_id]["result"] = context
            _tasks[task_id]["completed_at"] = datetime.now().isoformat()
            
        except Exception as e:
            # Mark workflow as failed
            _tasks[task_id]["status"] = "failed"
            _tasks[task_id]["error"] = str(e)
            _tasks[task_id]["failed_at"] = datetime.now().isoformat()
        
        return task_id
    
    @staticmethod
    def _topological_sort(nodes: List[Dict], edges: List[Dict]) -> List[str]:
        """
        Perform topological sort on workflow DAG
        
        Args:
            nodes: List of nodes
            edges: List of edges
            
        Returns:
            List of node IDs in execution order
        """
        from collections import defaultdict, deque
        
        # Build adjacency list and in-degree map
        graph = defaultdict(list)
        in_degree = {node["id"]: 0 for node in nodes}
        
        for edge in edges:
            source = edge.get("sourceNodeID")
            target = edge.get("targetNodeID")
            graph[source].append(target)
            in_degree[target] += 1
        
        # Kahn's algorithm
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        result = []
        
        while queue:
            node_id = queue.popleft()
            result.append(node_id)
            
            for neighbor in graph[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # Check for cycles
        if len(result) != len(nodes):
            raise ValueError("Workflow contains cycles")
        
        return result
    
    @staticmethod
    def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
        """Get task execution status"""
        return _tasks.get(task_id)
    
    @staticmethod
    def cancel_task(task_id: str) -> bool:
        """Cancel a running task"""
        if task_id in _tasks and _tasks[task_id]["status"] == "running":
            _tasks[task_id]["status"] = "cancelled"
            _tasks[task_id]["cancelled_at"] = datetime.now().isoformat()
            return True
        return False
