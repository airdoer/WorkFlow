import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)


class DistinctExecutor(BaseNodeExecutor):
    type = "distinct"

    def execute(self, config: dict, input_data: dict) -> dict:
        key_field = config.get("key", "")
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

        seen = set()
        result = []
        for item in input_list:
            if key_field and isinstance(item, dict):
                dedup_key = item.get(key_field, None)
                # Make hashable
                if isinstance(dedup_key, list):
                    dedup_key = tuple(dedup_key)
                if isinstance(dedup_key, dict):
                    dedup_key = str(dedup_key)
            else:
                dedup_key = item
                if isinstance(dedup_key, list):
                    dedup_key = tuple(dedup_key)
                if isinstance(dedup_key, dict):
                    dedup_key = str(dedup_key)

            try:
                hash(dedup_key)
            except TypeError:
                dedup_key = str(dedup_key)

            if dedup_key not in seen:
                seen.add(dedup_key)
                result.append(item)

        return {
            "__runtime_type__": "list",
            "__value__": result,
            "value": result,
            "count": len(result),
            "removedCount": len(input_list) - len(result),
        }
