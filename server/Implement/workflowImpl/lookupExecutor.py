import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)


class LookupExecutor(BaseNodeExecutor):
    type = "lookup"

    def execute(self, config: dict, input_data: dict) -> dict:
        lookup_key = input_data.get("key", config.get("key", ""))
        source = input_data.get("source", input_data.get("object", {}))

        if not lookup_key:
            return {"error": "Lookup key is required"}

        if not isinstance(source, dict):
            if isinstance(source, list):
                # Try to convert list to dict
                source_dict = {}
                for i, item in enumerate(source):
                    if isinstance(item, dict):
                        # Use first value as key if possible
                        first_val = next(iter(item.values()), None) if item else None
                        source_dict[str(first_val if first_val is not None else i)] = item
                    else:
                        source_dict[str(i)] = item
                source = source_dict
            else:
                return {"error": "Source must be a dict or list"}

        result = source.get(lookup_key, None)
        found = result is not None

        return {
            "__runtime_type__": "object" if isinstance(result, dict) else "list" if isinstance(result, list) else "string",
            "__value__": result,
            "value": result,
            "found": found,
            "key": lookup_key,
        }
