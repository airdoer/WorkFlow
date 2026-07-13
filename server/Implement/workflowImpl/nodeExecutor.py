from abc import ABC, abstractmethod


class BaseNodeExecutor(ABC):
    @property
    @abstractmethod
    def type(self) -> str:
        pass

    @abstractmethod
    def execute(self, config: dict, input_data: dict) -> dict:
        """Synchronous execution — no asyncio, compatible with gevent."""
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
    def run_node(cls, node_type: str, config: dict, input_data: dict) -> dict:
        executor = cls.get(node_type)
        if not executor:
            raise ValueError(f"Unknown node type: {node_type}")
        result = executor.execute(config, input_data)
        # Auto-inject Runtime Value markers if not already present
        return cls._inject_runtime_type(result, node_type)

    @classmethod
    def _inject_runtime_type(cls, result: dict, node_type: str) -> dict:
        """
        Automatically inject __runtime_type__ and __value__ markers
        for backward compatibility with old executors that don't set them.

        Rules:
        - If result already has __runtime_type__, leave it as-is (new executors)
        - If result has 'error' key, skip injection
        - Otherwise, infer type from the 'value' key or node_type heuristics
        """
        if not isinstance(result, dict):
            return result

        # Skip if already has runtime markers (new executors set them)
        if "__runtime_type__" in result:
            return result

        # Skip error results
        if "error" in result and "value" not in result:
            return result

        # Try to infer __runtime_type__ from result content
        runtime_type = cls._infer_runtime_type(result, node_type)
        if runtime_type:
            # Use the most appropriate 'value' key
            value = result.get("value",
                      result.get("jsonData",
                        result.get("content",
                          result.get("textOutput",
                            result.get("tableData", None)))))
            result["__runtime_type__"] = runtime_type
            if value is not None and "__value__" not in result:
                result["__value__"] = value

        return result

    @classmethod
    def _infer_runtime_type(cls, result: dict, node_type: str) -> str:
        """Infer __runtime_type__ from node type or result content."""

        # Direct type mapping for known node types
        type_map = {
            "string": "string",
            "bool": "boolean",
            "number": "number",
            "boolgate": "boolean",
            "prompt": "string",
            "llm": "string",
            "calculate": "number",
            "template": "string",
            "condition": "boolean",
            "if": "string",
            "loop": "list",
            "map": "list",
            "filter": "list",
            "reduce": "any",
            "sort": "list",
            "join": "list",
            "lookup": "any",
            "split": "list",
            "distinct": "list",
            "flatten": "list",
            "groupby": "object",
            "listbuilder": "list",
            "objectbuilder": "object",
            "dictbuilder": "object",
        }

        if node_type in type_map:
            return type_map[node_type]

        # Heuristic: check result keys
        value = result.get("value")
        if isinstance(value, list):
            return "list"
        if isinstance(value, dict):
            return "object"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)):
            return "number"
        if isinstance(value, str):
            return "string"

        # Check jsonData (JSON executor)
        json_data = result.get("jsonData")
        if json_data is not None:
            if isinstance(json_data, list):
                return "list"
            if isinstance(json_data, dict):
                return "object"

        # Check tableData (Excel executor)
        table_data = result.get("tableData")
        if table_data is not None:
            return "object"

        # Check content (Lua executor)
        content = result.get("content")
        if content is not None and isinstance(content, str):
            return "string"

        # Default
        return "any"

    @classmethod
    def list_executors(cls):
        return [{'type': k, 'class': v.__class__.__name__} for k, v in cls._executors.items()]
