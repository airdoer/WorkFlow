import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)


class SortExecutor(BaseNodeExecutor):
    type = "sort"

    def execute(self, config: dict, input_data: dict) -> dict:
        key_field = config.get("key", "")
        order = config.get("order", "asc")
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

        reverse = (order == "desc")

        try:
            if key_field:
                # Sort list of dicts by a field
                def sort_key(item):
                    if isinstance(item, dict):
                        val = item.get(key_field, None)
                    else:
                        val = item
                    # Handle None values: put them last
                    if val is None:
                        return (1, "")
                    return (0, val)

                result = sorted(input_list, key=sort_key, reverse=reverse)
            else:
                # Sort primitives
                def safe_key(item):
                    if item is None:
                        return (1, "")
                    return (0, item)

                result = sorted(input_list, key=safe_key, reverse=reverse)
        except TypeError as e:
            logger.warning("[Sort] Mixed types, fallback to string sort: %s", e)
            result = sorted(input_list, key=lambda x: str(x) if x is not None else "", reverse=reverse)

        return {
            "__runtime_type__": "list",
            "__value__": result,
            "value": result,
            "count": len(result),
        }
