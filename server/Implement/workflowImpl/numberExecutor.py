from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class NumberExecutor(BaseNodeExecutor):
    type = "number"

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        Number node: outputs a numeric value.
        - If connected via valueIn port, use upstream value
        - Otherwise, use config['value']
        """
        raw = input_data.get("valueIn")
        if raw is None:
            raw = config.get("value", 0)
        try:
            num_val = float(str(raw))
            # Return int if it's a whole number, else float
            if num_val == int(num_val):
                num_val = int(num_val)
        except (ValueError, TypeError):
            num_val = 0
        return {"value": num_val}
