import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)


class ListBuilderExecutor(BaseNodeExecutor):
    """
    List Builder: construct a list from dynamic arguments.

    Config:
        arguments: [{"name": "item1", "value": "val1"}, {"name": "item2", "value": "val2"}]

    Or from input_data ports (item1, item2, ...).
    """

    type = "listbuilder"

    def execute(self, config: dict, input_data: dict) -> dict:
        arguments = config.get("arguments", [])

        result = []

        # Priority 1: Dynamic arguments from config
        if arguments and isinstance(arguments, list):
            for arg in arguments:
                if isinstance(arg, dict):
                    name = arg.get("name", "")
                    value = arg.get("value", None)
                    # Check if value comes from connection
                    if arg.get("source") == "connection" and name in input_data:
                        value = input_data.get(name, value)
                    result.append(value)
        else:
            # Priority 2: Collect all input_data values (excluding internal keys)
            for key in sorted(input_data.keys()):
                if not key.startswith("__") and key not in ("list", "result", "value"):
                    result.append(input_data[key])

        return {
            "__runtime_type__": "list",
            "__value__": result,
            "value": result,
            "count": len(result),
        }
