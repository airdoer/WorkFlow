import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor
from Implement.workflowImpl.expressionEngine import get_expression_engine

logger = logging.getLogger(__name__)


class FilterExecutor(BaseNodeExecutor):
    type = "filter"

    def execute(self, config: dict, input_data: dict) -> dict:
        expression = config.get("expression", "")
        input_list = input_data.get("list", [])

        if not input_list:
            input_list = input_data.get("result", [])
        if not input_list:
            input_list = input_data.get("value", [])
        if not isinstance(input_list, list):
            input_list = [input_list] if input_list else []

        if not expression:
            return {"error": "Expression is required for Filter node"}

        engine = get_expression_engine()
        result = []
        for index, item in enumerate(input_list):
            try:
                ctx = {"item": item, "index": index, **input_data}
                if engine.evaluate_boolean(expression, ctx):
                    result.append(item)
            except Exception as e:
                logger.warning("[Filter] Error evaluating item %s: %s", index, e)

        return {
            "__runtime_type__": "list",
            "__value__": result,
            "value": result,
            "count": len(result),
            "removedCount": len(input_list) - len(result),
        }
