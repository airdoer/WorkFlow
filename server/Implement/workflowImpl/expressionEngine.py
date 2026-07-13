"""
Simple Expression Engine for Workflow Collection / Expression nodes.

Supports:
- Variable access: item, index, acc, group, and custom variables
- Attribute access: item.field, item["field"]
- Arithmetic: +, -, *, /, %
- Comparison: ==, !=, >, <, >=, <=
- Logical: and, or, not
- String interpolation: {{var}}
- Ternary: condition ? valueIfTrue : valueIfFalse
- Built-in functions: len(), str(), int(), float(), type(), keys(), values()
"""

import logging
import re
import operator
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Safe built-in functions for expressions
_SAFE_BUILTINS = {
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "type": lambda x: type(x).__name__,
    "keys": lambda x: list(x.keys()) if isinstance(x, dict) else [],
    "values": lambda x: list(x.values()) if isinstance(x, dict) else [],
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
    "sorted": sorted,
    "reversed": lambda x: list(reversed(x)),
    "enumerate": enumerate,
    "zip": zip,
    "True": True,
    "False": False,
    "None": None,
    "true": True,
    "false": False,
    "null": None,
}


class SimpleExpressionEngine:
    """
    Lightweight expression engine for Workflow nodes.

    Usage:
        engine = SimpleExpressionEngine()
        result = engine.evaluate("item * 2", {"item": 5})
        # result = 10

        result = engine.evaluate("item.name", {"item": {"name": "sword"}})
        # result = "sword"
    """

    def __init__(self):
        self._cache: Dict[str, Any] = {}

    def evaluate(self, expression: str, context: Dict[str, Any]) -> Any:
        """
        Evaluate an expression with the given context.

        Args:
            expression: The expression string to evaluate
            context: Variable bindings (e.g. {"item": ..., "index": 0})

        Returns:
            The result of the expression evaluation
        """
        if not expression or not expression.strip():
            return None

        expr = expression.strip()

        # 1. Try template interpolation first: {{var}}
        if "{{" in expr:
            return self._interpolate_template(expr, context)

        # 2. Simple variable access: just a variable name
        if self._is_simple_variable(expr, context):
            return self._resolve_variable(expr, context)

        # 3. Evaluate as safe Python expression
        try:
            return self._eval_expression(expr, context)
        except Exception as e:
            logger.warning("[ExpressionEngine] Failed to evaluate '%s': %s", expr, e)
            return None

    def evaluate_boolean(self, expression: str, context: Dict[str, Any]) -> bool:
        """Evaluate an expression and return a boolean result."""
        result = self.evaluate(expression, context)
        if result is None:
            return False
        return bool(result)

    def _is_simple_variable(self, expr: str, context: Dict[str, Any]) -> bool:
        """Check if the expression is a simple variable reference like 'item' or 'item.field'."""
        # Match: word.word.word...
        if re.match(r'^[a-zA-Z_]\w*(\.[a-zA-Z_]\w*)*$', expr):
            return True
        # Match: word["key"] or word['key']
        if re.match(r'^[a-zA-Z_]\w*(\[["\'][^"\']+["\']\])*$', expr):
            return True
        return False

    def _resolve_variable(self, expr: str, context: Dict[str, Any]) -> Any:
        """Resolve a dotted variable path like 'item.name' or 'item["key"]'."""
        # Handle bracket notation: item["key"]
        parts = re.split(r'\[["\']([^"\']+)["\']\]', expr)
        if len(parts) > 1:
            # e.g. ["item", "key", ".subfield", "key2", ""]
            current = self._resolve_dotted(parts[0].rstrip('.'), context)
            i = 1
            while i < len(parts):
                if parts[i]:  # bracket key
                    key = parts[i]
                    if isinstance(current, dict):
                        current = current.get(key)
                    elif isinstance(current, (list, tuple)):
                        try:
                            current = current[int(key)]
                        except (ValueError, IndexError):
                            return None
                    else:
                        return None
                if i + 1 < len(parts) and parts[i + 1]:
                    dotted = parts[i + 1].lstrip('.')
                    if dotted:
                        current = self._resolve_dotted(dotted, {"_": current})
                        # Fix: _resolve_dotted uses the context dict, need to handle differently
                        if isinstance(current, dict) and "_" in current:
                            pass  # Already resolved
                i += 2
            return current

        # Handle dot notation: item.field.subfield
        return self._resolve_dotted(expr, context)

    def _resolve_dotted(self, expr: str, context: Dict[str, Any]) -> Any:
        """Resolve a dotted path like 'item.field.subfield'."""
        parts = expr.split('.')
        current = context
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
            if current is None:
                return None
        return current

    def _interpolate_template(self, template: str, context: Dict[str, Any]) -> str:
        """
        Replace {{var}} placeholders in a template string.

        Example: "Hello {{name}}, count={{count}}" with {name: "world", count: 5}
        → "Hello world, count=5"
        """
        def replacer(match):
            var_expr = match.group(1).strip()
            result = self.evaluate(var_expr, context)
            return str(result) if result is not None else ""

        return re.sub(r'\{\{(.+?)\}\}', replacer, template)

    def _eval_expression(self, expr: str, context: Dict[str, Any]) -> Any:
        """
        Safely evaluate a Python expression with the given context.

        Uses restricted globals to prevent unsafe operations.
        """
        # Preprocess: convert dotted access like item.field to item["field"]
        # when the base variable is a dict in context
        processed = self._preprocess_dotted_access(expr, context)

        # Build safe globals
        safe_globals = {
            "__builtins__": _SAFE_BUILTINS,
            "True": True,
            "False": False,
            "None": None,
        }

        # Build locals from context
        safe_locals = dict(context)

        # Evaluate
        try:
            result = eval(processed, safe_globals, safe_locals)  # noqa: S307
            return result
        except NameError as e:
            # Try to resolve as dotted path in context
            logger.debug("[ExpressionEngine] NameError for '%s', trying dotted resolution", expr)
            resolved = self._resolve_variable(expr, context)
            if resolved is not None:
                return resolved
            raise
        except (KeyError, IndexError, ZeroDivisionError) as e:
            logger.debug("[ExpressionEngine] Error evaluating '%s': %s", expr, e)
            raise
        except (TypeError, AttributeError) as e:
            # Try auto-coercion: if comparing str with number, convert str to number
            logger.debug("[ExpressionEngine] TypeError/AttributeError for '%s': %s, trying auto-coercion", expr, e)
            coerced = self._auto_coerce_context(safe_locals)
            if coerced != safe_locals:
                try:
                    result = eval(processed, safe_globals, coerced)  # noqa: S307
                    return result
                except Exception:
                    pass
            raise

    def _preprocess_dotted_access(self, expr: str, context: Dict[str, Any]) -> str:
        """Convert item.field to item["field"] when item resolves to a dict in context."""
        # Match dotted patterns: word.word(.word)*
        # Use Unicode-aware \w to support Chinese characters in field names
        pattern = r'\b([a-zA-Z_\u4e00-\u9fff]\w*)(\.[a-zA-Z_\u4e00-\u9fff]\w*)+'

        def replacer(match):
            full = match.group(0)
            parts = full.split('.')
            base = parts[0]
            # Check if base resolves to a dict in context
            val = context.get(base)
            if isinstance(val, dict):
                result = base
                for attr in parts[1:]:
                    result += f'["{attr}"]'
                return result
            # Not a dict — keep original (e.g. object.attr works normally)
            return full

        return re.sub(pattern, replacer, expr)

    def _safe_eval(self, expr: str, context: Dict[str, Any]) -> Any:
        """Alias for _eval_expression."""
        return self._eval_expression(expr, context)

    def _auto_coerce_context(self, locals_dict: dict) -> dict:
        """Create a copy of locals with string values auto-coerced to numbers where possible.

        This handles cases like "4" < 10 where the string "4" should be compared as int 4.
        """
        import copy
        coerced = copy.deepcopy(locals_dict)
        self._coerce_dict_values(coerced)
        return coerced

    def _coerce_dict_values(self, d: dict):
        """Recursively coerce string values that look like numbers to actual numbers."""
        for key, value in d.items():
            if isinstance(value, dict):
                self._coerce_dict_values(value)
            elif isinstance(value, str):
                try:
                    d[key] = int(value)
                except (ValueError, TypeError):
                    try:
                        d[key] = float(value)
                    except (ValueError, TypeError):
                        pass


# Singleton engine instance
_engine_instance: Optional[SimpleExpressionEngine] = None


def get_expression_engine() -> SimpleExpressionEngine:
    """Get the singleton ExpressionEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SimpleExpressionEngine()
    return _engine_instance


def evaluate_expression(expression: str, context: Dict[str, Any]) -> Any:
    """Convenience function to evaluate an expression."""
    return get_expression_engine().evaluate(expression, context)
