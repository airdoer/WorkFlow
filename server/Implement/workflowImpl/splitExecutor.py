import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)


class SplitExecutor(BaseNodeExecutor):
    type = "split"

    def execute(self, config: dict, input_data: dict) -> dict:
        field = config.get("field", "")
        chunk_size_str = config.get("chunkSize", "")
        input_list = input_data.get("list", [])

        if not input_list:
            input_list = input_data.get("result", [])
        if not input_list:
            input_list = input_data.get("value", [])
        if not isinstance(input_list, list):
            input_list = [input_list] if input_list else []

        if not input_list:
            return {
                "__runtime_type__": "list",
                "__value__": [],
                "value": [],
                "count": 0,
            }

        # Mode 1: Split by field (flatten a field in list of dicts)
        if field:
            result = []
            for item in input_list:
                if isinstance(item, dict):
                    sub = item.get(field, [])
                elif isinstance(item, (list, tuple)):
                    sub = item
                else:
                    sub = [item]
                if isinstance(sub, list):
                    result.extend(sub)
                else:
                    result.append(sub)
            return {
                "__runtime_type__": "list",
                "__value__": result,
                "value": result,
                "count": len(result),
            }

        # Mode 2: Split into chunks
        if chunk_size_str:
            try:
                chunk_size = int(chunk_size_str)
                if chunk_size <= 0:
                    chunk_size = 1
            except ValueError:
                chunk_size = 1

            result = []
            for i in range(0, len(input_list), chunk_size):
                result.append(input_list[i:i + chunk_size])

            return {
                "__runtime_type__": "list",
                "__value__": result,
                "value": result,
                "count": len(result),
            }

        # No field or chunk_size: return as-is
        return {
            "__runtime_type__": "list",
            "__value__": input_list,
            "value": input_list,
            "count": len(input_list),
        }
