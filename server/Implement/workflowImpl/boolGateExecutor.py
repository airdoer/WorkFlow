from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class BoolGateExecutor(BaseNodeExecutor):
    type = "boolgate"

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        BoolGate 节点：布尔门控执行器。
        - 当输入 Bool 值为 True 时，输出 True 并继续执行后续节点。
        - 当输入 Bool 值为 False 时，抛出异常中断流程。

        输入:
          - valueIn: bool（通过连线从上游节点获取）

        输出:
          - value: bool（仅当 True 时才有输出）
        """
        raw = input_data.get('valueIn')
        if raw is None:
            raw = config.get('value', False)

        # 规范化为 bool
        if isinstance(raw, str):
            bool_val = raw.lower() in ('true', '1', 'yes')
        else:
            bool_val = bool(raw)

        if not bool_val:
            raise ValueError("BoolGate: 输入值为 False，流程中断")

        return {'value': True}
