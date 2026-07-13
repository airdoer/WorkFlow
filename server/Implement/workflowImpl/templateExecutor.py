import logging
import re
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor
from Implement.workflowImpl.expressionEngine import get_expression_engine

logger = logging.getLogger(__name__)


class TemplateExecutor(BaseNodeExecutor):
    type = "template"

    def execute(self, config: dict, input_data: dict) -> dict:
        template = config.get("template", config.get("expression", ""))
        arguments = config.get("arguments", [])
        separator = config.get("separator", "\n")

        if not template:
            return {"error": "Template is required"}

        # Build context from dynamic arguments
        context = {}
        if arguments and isinstance(arguments, list):
            for arg in arguments:
                if isinstance(arg, dict):
                    name = arg.get("name", "")
                    value = arg.get("value", None)
                    if arg.get("source") == "connection" and name in input_data:
                        value = input_data.get(name, value)
                    context[name] = value

        # Also include input_data for inline variables
        context.update(input_data)

        engine = get_expression_engine()
        try:
            # Check for {{#each list}}...{{/each}} block syntax
            each_pattern = re.compile(
                r'\{\{#each\s+(\w+)\}\}(.*?)\{\{/each\}\}',
                re.DOTALL
            )

            def replace_each_block(match):
                list_var = match.group(1).strip()
                body = match.group(2)
                # Resolve the list variable from context
                items = context.get(list_var)
                if items is None:
                    # Try common keys
                    for key in ("list", "value", "result", "rows"):
                        if key in context:
                            items = context[key]
                            break
                if not isinstance(items, list):
                    if items is not None:
                        items = [items]
                    else:
                        items = []

                parts = []
                for idx, item in enumerate(items):
                    item_ctx = dict(context)
                    item_ctx["item"] = item
                    item_ctx["index"] = idx
                    # Also flatten item fields into context if item is a dict
                    if isinstance(item, dict):
                        item_ctx.update(item)
                    rendered = engine._interpolate_template(body, item_ctx)
                    parts.append(rendered)
                return separator.join(parts)

            # First, process all {{#each}} blocks
            result = each_pattern.sub(replace_each_block, template)

            # Then, process remaining {{var}} interpolations
            if "{{" in result:
                result = engine._interpolate_template(result, context)

        except Exception as e:
            logger.exception("[Template] Error evaluating: %s", e)
            return {"error": f"Template evaluation error: {e}"}

        return {
            "__runtime_type__": "string",
            "__value__": result,
            "value": result,
        }
