import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor
from Implement.workflowImpl.expressionEngine import get_expression_engine

logger = logging.getLogger(__name__)


class CalculateExecutor(BaseNodeExecutor):
    type = "calculate"

    def execute(self, config: dict, input_data: dict) -> dict:
        expression = config.get("expression", "")
        arguments = config.get("arguments", [])

        if not expression:
            return {"error": "Expression is required for Calculate node"}

        # Build context from dynamic arguments
        context = {}
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
                    context[name] = value

        # Also include input_data for inline variables
        context.update(input_data)

        engine = get_expression_engine()
        try:
            result = engine.evaluate(expression, context)
        except Exception as e:
            logger.exception("[Calculate] Error evaluating '%s': %s", expression, e)
            return {"error": f"Expression evaluation error: {e}"}

        return {
            "__runtime_type__": "number" if isinstance(result, (int, float)) else "string",
            "__value__": result,
            "value": result,
        }
