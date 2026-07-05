"""
Base Node Executor and Executor Manager
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseNodeExecutor(ABC):
    """Base class for all node executors"""
    
    @property
    @abstractmethod
    def type(self) -> str:
        """Node type identifier (excel, lua, json, prompt)"""
        pass
    
    @abstractmethod
    async def execute(self, config: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the node with given config and input data
        
        Args:
            config: Node configuration from frontend
            input_data: Input data from upstream nodes
            
        Returns:
            Output data for downstream nodes
        """
        pass


class ExecutorManager:
    """Manages all node executors"""
    
    _executors: Dict[str, BaseNodeExecutor] = {}
    
    @classmethod
    def register(cls, executor: BaseNodeExecutor):
        """Register a node executor"""
        cls._executors[executor.type] = executor
        print(f"Registered executor: {executor.type}")
    
    @classmethod
    def get(cls, node_type: str) -> Optional[BaseNodeExecutor]:
        """Get executor by node type"""
        return cls._executors.get(node_type)
    
    @classmethod
    async def run_node(cls, node_type: str, config: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a node by type
        
        Args:
            node_type: Type of the node (excel, lua, json, prompt)
            config: Node configuration
            input_data: Input from upstream nodes
            
        Returns:
            Node execution output
            
        Raises:
            ValueError: If node type is not registered
        """
        executor = cls.get(node_type)
        if not executor:
            raise ValueError(f"Unknown node type: {node_type}")
        
        return await executor.execute(config, input_data)
    
    @classmethod
    def list_executors(cls) -> list:
        """List all registered executor types"""
        return list(cls._executors.keys())
