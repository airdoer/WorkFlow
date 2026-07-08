from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class BoolExecutor(BaseNodeExecutor):
    type = "bool"

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        Bool node: outputs a boolean value.
        - If connected via valueIn port, use upstream value
        - Otherwise, use config['value']
        """
        raw = input_data.get("valueIn")
        if raw is None:
            raw = config.get("value", False)
        # Normalize to bool
        if isinstance(raw, str):
            bool_val = raw.lower() in ("true", "1", "yes")
        else:
            bool_val = bool(raw)
        return {"value": bool_val}
