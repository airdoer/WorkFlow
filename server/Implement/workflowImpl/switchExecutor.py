import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor
from Implement.workflowImpl.expressionEngine import get_expression_engine

logger = logging.getLogger(__name__)


class SwitchExecutor(BaseNodeExecutor):
    """
    Switch node: multi-way branching based on rules.

    Config:
        rules: [
            {"id": "1", "expression": "value == 'A'", "output": 1},
            {"id": "2", "expression": "value == 'B'", "output": 2},
        ]
    """

    type = "switch"

    def execute(self, config: dict, input_data: dict) -> dict:
        rules = config.get("rules", [])
        value = input_data.get("value", None)

        if not rules:
            # Default: match against static values
            return self._static_match(value, config, input_data)

        engine = get_expression_engine()
        context = dict(input_data)
        context["value"] = value

        matched_rule = None
        for rule in rules:
            if isinstance(rule, dict):
                expr = rule.get("expression", "")
                if expr:
                    try:
                        if engine.evaluate_boolean(expr, context):
                            matched_rule = rule
                            break
                    except Exception as e:
                        logger.warning("[Switch] Rule %s error: %s", rule.get("id", "?"), e)

        if matched_rule:
            output_index = matched_rule.get("output", 0)
            return {
                "__runtime_type__": "string",
                "__value__": value,
                "value": value,
                "matchedRule": matched_rule.get("id", ""),
                "output": output_index,
                "branch": f"case{output_index}",
            }
        else:
            return {
                "__runtime_type__": "string",
                "__value__": value,
                "value": value,
                "matchedRule": None,
                "output": 0,
                "branch": "default",
            }

    def _static_match(self, value, config: dict, input_data: dict) -> dict:
        """Simple static value matching (no rules configured)."""
        cases = config.get("cases", [])

        for i, case in enumerate(cases):
            case_value = case.get("value", None) if isinstance(case, dict) else case
            if value == case_value:
                return {
                    "__runtime_type__": "string",
                    "__value__": value,
                    "value": value,
                    "matchedRule": i,
                    "output": i + 1,
                    "branch": f"case{i + 1}",
                }

        return {
            "__runtime_type__": "string",
            "__value__": value,
            "value": value,
            "matchedRule": None,
            "output": 0,
            "branch": "default",
        }
