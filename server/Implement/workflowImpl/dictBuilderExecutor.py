import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)


class DictBuilderExecutor(BaseNodeExecutor):
    """
    Dictionary Builder: construct a dictionary from key-value pairs.
    Same as Object Builder but oriented toward game config scenario (Lua Table / config dict).

    Config:
        arguments: [{"name": "1001", "value": {"name":"宝刀","quality":5}}, ...]
    """

    type = "dictbuilder"

    def execute(self, config: dict, input_data: dict) -> dict:
        arguments = config.get("arguments", [])

        result = {}

        if arguments and isinstance(arguments, list):
            for arg in arguments:
                if isinstance(arg, dict):
                    name = arg.get("name", "")
                    value = arg.get("value", None)
                    if arg.get("source") == "connection" and name in input_data:
                        value = input_data.get(name, value)
                    # Try to parse value
                    if isinstance(value, str):
                        try:
                            parsed = eval(value, {"__builtins__": {}}, {})  # noqa: S307
                            value = parsed
                        except Exception:
                            pass
                    result[name] = value
        else:
            for key, value in input_data.items():
                if not key.startswith("__") and key not in ("list", "result", "value", "object"):
                    result[key] = value

        return {
            "__runtime_type__": "object",
            "__value__": result,
            "value": result,
            "keyCount": len(result),
        }
