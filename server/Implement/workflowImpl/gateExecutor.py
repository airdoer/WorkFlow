from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class GateExecutor(BaseNodeExecutor):
    type = "gate"

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        Gate 节点：条件门控执行器。
        - 接受两个输入：value (任意类型) 和 enabled (布尔)
        - 当 enabled=True 时，透传 value 到下游
        - 当 enabled=False 时，抛出异常中断流程
          （执行引擎会静默跳过所有下游节点）

        输入:
          - valueIn: any（通过连线从上游节点获取）
          - enabledIn: bool（通过连线从上游获取，或使用 config['enabled']）

        输出:
          - value: any（与输入 value 同类型，仅 enabled=True 时）
        """
        # Resolve enabled
        enabled_raw = input_data.get('enabledIn')
        if enabled_raw is None:
            enabled_raw = config.get('enabled', False)
        if isinstance(enabled_raw, str):
            enabled = enabled_raw.lower() in ('true', '1', 'yes')
        else:
            enabled = bool(enabled_raw)

        if not enabled:
            raise ValueError("Gate: 门控关闭")

        # Gate open — pass through value
        value = input_data.get('valueIn')
        return {'value': value}
