import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)


class IfExecutor(BaseNodeExecutor):
    """
    If node: conditional branching.

    True → output result = trueValue, branch = "true"
    False → output result = falseValue, branch = "false"

    Unlike BoolGate, If does NOT error on false — it just takes the other branch.
    """

    type = "if"

    def execute(self, config: dict, input_data: dict) -> dict:
        # Get condition
        condition = input_data.get("condition", None)

        # If no direct condition, try to evaluate expression
        if condition is None:
            expression = config.get("expression", "")
            if expression:
                from Implement.workflowImpl.expressionEngine import get_expression_engine
                engine = get_expression_engine()
                context = dict(input_data)
                # Add config values to context
                for k, v in config.items():
                    if k not in ("expression", "type") and not k.startswith("_"):
                        context[k] = v
                condition = engine.evaluate_boolean(expression, context)
            else:
                # Fallback: check any boolean-like value in input_data
                for key, val in input_data.items():
                    if not key.startswith("__") and isinstance(val, bool):
                        condition = val
                        break

        # Normalize condition
        if isinstance(condition, str):
            condition = condition.lower() in ("true", "1", "yes")
        condition = bool(condition) if condition is not None else False

        true_value = input_data.get("trueValue", config.get("trueValue", None))
        false_value = input_data.get("falseValue", config.get("falseValue", None))

        result = true_value if condition else false_value

        return {
            "__runtime_type__": "object" if isinstance(result, dict) else "list" if isinstance(result, list) else "string",
            "__value__": result,
            "value": result,
            "result": result,
            "branch": "true" if condition else "false",
            "condition": condition,
        }
