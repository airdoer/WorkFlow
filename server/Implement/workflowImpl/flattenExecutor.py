import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)


class FlattenExecutor(BaseNodeExecutor):
    type = "flatten"

    def execute(self, config: dict, input_data: dict) -> dict:
        input_list = input_data.get("list", [])

        if not input_list:
            input_list = input_data.get("result", [])
        if not input_list:
            input_list = input_data.get("value", [])
        if not isinstance(input_list, list):
            input_list = [input_list] if input_list else []

        result = self._deep_flatten(input_list)

        return {
            "__runtime_type__": "list",
            "__value__": result,
            "value": result,
            "count": len(result),
        }

    @staticmethod
    def _deep_flatten(nested_list) -> list:
        """Deep flatten a nested list."""
        result = []
        for item in nested_list:
            if isinstance(item, list):
                result.extend(FlattenExecutor._deep_flatten(item))
            elif isinstance(item, (list, tuple)):
                result.extend(FlattenExecutor._deep_flatten(list(item)))
            else:
                result.append(item)
        return result
