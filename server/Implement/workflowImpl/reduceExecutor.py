import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor
from Implement.workflowImpl.expressionEngine import get_expression_engine

logger = logging.getLogger(__name__)


class ReduceExecutor(BaseNodeExecutor):
    type = "reduce"

    def execute(self, config: dict, input_data: dict) -> dict:
        expression = config.get("expression", "")
        initial_value_str = config.get("initialValue", "")
        input_list = input_data.get("list", [])

        if not input_list:
            input_list = input_data.get("result", [])
        if not input_list:
            input_list = input_data.get("value", [])
        if not isinstance(input_list, list):
            input_list = [input_list] if input_list else []

        if not expression:
            return {"error": "Expression is required for Reduce node"}

        # Parse initial value
        acc = None
        if initial_value_str:
            try:
                acc = eval(initial_value_str, {"__builtins__": {}}, {})  # noqa: S307
            except Exception:
                try:
                    acc = int(initial_value_str)
                except ValueError:
                    try:
                        acc = float(initial_value_str)
                    except ValueError:
                        acc = initial_value_str

        engine = get_expression_engine()
        for index, item in enumerate(input_list):
            try:
                ctx = {"item": item, "index": index, "acc": acc, **input_data}
                acc = engine.evaluate(expression, ctx)
            except Exception as e:
                logger.warning("[Reduce] Error at item %s: %s", index, e)

        # Determine runtime type
        if isinstance(acc, list):
            rt_type = "list"
        elif isinstance(acc, dict):
            rt_type = "object"
        elif isinstance(acc, (int, float)):
            rt_type = "number"
        elif isinstance(acc, str):
            rt_type = "string"
        elif isinstance(acc, bool):
            rt_type = "boolean"
        else:
            rt_type = "null"

        return {
            "__runtime_type__": rt_type,
            "__value__": acc,
            "value": acc,
        }
