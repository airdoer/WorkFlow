from abc import ABC, abstractmethod


class BaseNodeExecutor(ABC):
    @property
    @abstractmethod
    def type(self) -> str:
        pass

    @abstractmethod
    async def execute(self, config: dict, input_data: dict) -> dict:
        pass


class ExecutorManager:
    _executors = {}

    @classmethod
    def register(cls, executor):
        cls._executors[executor.type] = executor

    @classmethod
    def get(cls, node_type: str):
        return cls._executors.get(node_type)

    @classmethod
    async def run_node(cls, node_type: str, config: dict, input_data: dict) -> dict:
        executor = cls.get(node_type)
        if not executor:
            raise ValueError(f"Unknown node type: {node_type}")
        return await executor.execute(config, input_data)

    @classmethod
    def list_executors(cls):
        return [{'type': k, 'class': v.__class__.__name__} for k, v in cls._executors.items()]
