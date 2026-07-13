import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor
from Implement.workflowImpl.expressionEngine import get_expression_engine

logger = logging.getLogger(__name__)


class GroupByExecutor(BaseNodeExecutor):
    type = "groupby"

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
            return {"error": "Expression is required for GroupBy node"}

        engine = get_expression_engine()
        groups = {}

        for index, item in enumerate(input_list):
            try:
                ctx = {"item": item, "index": index, **input_data}
                key = engine.evaluate(expression, ctx)
                # Make key hashable
                if isinstance(key, dict):
                    key = str(key)
                elif isinstance(key, list):
                    key = tuple(key)

                key_str = str(key) if key is not None else "__null__"
                if key_str not in groups:
                    groups[key_str] = []
                groups[key_str].append(item)
            except Exception as e:
                logger.warning("[GroupBy] Error evaluating item %s: %s", index, e)

        return {
            "__runtime_type__": "object",
            "__value__": groups,
            "value": groups,
            "groupCount": len(groups),
            "totalCount": len(input_list),
        }
