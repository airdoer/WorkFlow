import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor
from Implement.workflowImpl.expressionEngine import get_expression_engine

logger = logging.getLogger(__name__)


class ConditionExecutor(BaseNodeExecutor):
    type = "condition"

    def execute(self, config: dict, input_data: dict) -> dict:
        expression = config.get("expression", "")
        arguments = config.get("arguments", [])

        if not expression:
            # Also accept direct condition input
            condition_val = input_data.get("condition", input_data.get("value", None))
            if condition_val is not None:
                result = bool(condition_val)
                return {
                    "__runtime_type__": "boolean",
                    "__value__": result,
                    "value": result,
                    "result": result,
                    "branch": "true" if result else "false",
                }
            return {"error": "Expression or condition input is required"}

        # Build context from dynamic arguments
        context = {}
        if arguments and isinstance(arguments, list):
            for arg in arguments:
                if isinstance(arg, dict):
                    name = arg.get("name", "")
                    value = arg.get("value", None)
                    if arg.get("source") == "connection" and name in input_data:
                        value = input_data.get(name, value)
                    if isinstance(value, str):
                        try:
                            parsed = eval(value, {"__builtins__": {}}, {})  # noqa: S307
                            value = parsed
                        except Exception:
                            pass
                    context[name] = value

        context.update(input_data)

        engine = get_expression_engine()
        try:
            result = engine.evaluate_boolean(expression, context)
        except Exception as e:
            logger.exception("[Condition] Error evaluating '%s': %s", expression, e)
            return {"error": f"Condition evaluation error: {e}"}

        return {
            "__runtime_type__": "boolean",
            "__value__": result,
            "value": result,
            "result": result,
            "branch": "true" if result else "false",
        }
