import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)


class ObjectBuilderExecutor(BaseNodeExecutor):
    """
    Object Builder: construct an object from key-value pairs.

    Config:
        arguments: [{"name": "id", "value": "1001"}, {"name": "name", "value": "宝刀"}]

    Or from input_data ports (value_1, value_2, ... with names from config).
    """

    type = "objectbuilder"

    def execute(self, config: dict, input_data: dict) -> dict:
        arguments = config.get("arguments", [])

        result = {}

        if arguments and isinstance(arguments, list):
            for arg in arguments:
                if isinstance(arg, dict):
                    name = arg.get("name", "")
                    value = arg.get("value", None)
                    # Check if value comes from connection
                    if arg.get("source") == "connection" and name in input_data:
                        value = input_data.get(name, value)
                    # Try to parse value type
                    if isinstance(value, str):
                        try:
                            parsed = eval(value, {"__builtins__": {}}, {})  # noqa: S307
                            value = parsed
                        except Exception:
                            pass
                    result[name] = value
        else:
            # Collect from input_data
            for key, value in input_data.items():
                if not key.startswith("__") and key not in ("list", "result", "value", "object"):
                    result[key] = value

        return {
            "__runtime_type__": "object",
            "__value__": result,
            "value": result,
            "keyCount": len(result),
        }
