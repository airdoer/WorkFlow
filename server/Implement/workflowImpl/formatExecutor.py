"""
格式化 (Format) 节点执行器 — 字符串格式化拼接。

将模板字符串中的 {{var}} 占位符替换为对应变量值。
变量来源：config 中的字段（手动填入）+ input_data 中连线传入的值。

模板示例：http://{{ip}}:7800/c7_online_{{serverId}}
输入：
  config.ip = "10.73.14.121"  （手动填入）
  input_data.serverId = "1801" （连线传入）
→ 输出: http://10.73.14.121:7800/c7_online_1801
"""
import logging
import re
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)


class FormatExecutor(BaseNodeExecutor):
    type = "format"

    def execute(self, config: dict, input_data: dict) -> dict:
        template = config.get('template', '')
        if not template:
            return {"error": "格式模板不能为空"}

        # Build variable context from config fields + input_data
        context = {}

        # Config values (manual input, e.g. config.ip = "10.73.14.121")
        # Skip meta fields that are not actual variable values
        _skip_keys = {'template', 'variables'}
        for k, v in config.items():
            if k not in _skip_keys and v is not None and str(v).strip():
                context[k] = str(v)

        # Input data (from connections, e.g. input_data.serverId = "1801")
        # Connection values take priority over config
        for k, v in input_data.items():
            if v is not None and str(v).strip():
                context[k] = str(v)

        # Replace all {{var}} placeholders
        def replace_var(match):
            var_name = match.group(1)
            value = context.get(var_name)
            if value is not None:
                return value
            logger.warning("[Format] Variable '{{%s}}' not found in context, keeping placeholder", var_name)
            return match.group(0)

        try:
            result = re.sub(r'\{\{(\w+)\}\}', replace_var, template)
        except Exception as e:
            logger.exception("[Format] Error processing template: %s", e)
            return {"error": f"格式化错误: {e}"}

        return {
            "__runtime_type__": "string",
            "__value__": result,
            "value": result,
        }
