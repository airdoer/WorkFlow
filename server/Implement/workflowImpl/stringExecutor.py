from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class StringExecutor(BaseNodeExecutor):
    type = "string"

    async def execute(self, config: dict, input_data: dict) -> dict:
        """
        String node: outputs a string value.
        - If connected via valueIn port, use upstream value (passed in input_data)
        - Otherwise, use config['value']
        """
        raw = input_data.get("valueIn")
        if raw is None:
            raw = config.get("value", "")
        return {"value": str(raw)}
