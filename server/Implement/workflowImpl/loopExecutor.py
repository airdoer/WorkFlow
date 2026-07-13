import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor
from Implement.workflowImpl.expressionEngine import get_expression_engine

logger = logging.getLogger(__name__)


class LoopExecutor(BaseNodeExecutor):
    """
    Loop node: iterate over items or while condition is true.

    Modes:
    - for_each: iterate over each item in a list
    - while: continue while expression evaluates to true
    - count: run N times
    """

    type = "loop"

    def execute(self, config: dict, input_data: dict) -> dict:
        mode = config.get("mode", "for_each")
        max_iterations = int(config.get("maxIterations", 1000))
        expression = config.get("expression", "")

        if mode == "for_each":
            return self._for_each(input_data, max_iterations)
        elif mode == "while":
            return self._while(expression, input_data, max_iterations)
        elif mode == "count":
            count = int(config.get("count", input_data.get("count", 0)))
            return self._count_loop(count, max_iterations)
        else:
            return {"error": f"Unknown loop mode: {mode}"}

    def _for_each(self, input_data: dict, max_iterations: int) -> dict:
        """Iterate over each item in a list."""
        input_list = input_data.get("list", [])
        if not input_list:
            input_list = input_data.get("result", [])
        if not input_list:
            input_list = input_data.get("value", [])
        if not isinstance(input_list, list):
            input_list = [input_list] if input_list else []

        iterations = min(len(input_list), max_iterations)
        result = input_list[:iterations]

        return {
            "__runtime_type__": "list",
            "__value__": result,
            "value": result,
            "iterations": iterations,
            "mode": "for_each",
        }

    def _while(self, expression: str, input_data: dict, max_iterations: int) -> dict:
        """Continue while expression evaluates to true."""
        if not expression:
            return {"error": "Expression is required for while loop"}

        engine = get_expression_engine()
        result = []
        iterations = 0
        context = dict(input_data)

        while iterations < max_iterations:
            try:
                should_continue = engine.evaluate_boolean(expression, context)
                if not should_continue:
                    break
            except Exception:
                break

            result.append(context.get("item", context.get("value", None)))
            context["index"] = iterations
            iterations += 1

        return {
            "__runtime_type__": "list",
            "__value__": result,
            "value": result,
            "iterations": iterations,
            "mode": "while",
        }

    def _count_loop(self, count: int, max_iterations: int) -> dict:
        """Run loop N times."""
        iterations = min(count, max_iterations)
        result = list(range(iterations))

        return {
            "__runtime_type__": "list",
            "__value__": result,
            "value": result,
            "iterations": iterations,
            "mode": "count",
        }
