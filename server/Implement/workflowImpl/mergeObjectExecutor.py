import json
import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)


class MergeObjectExecutor(BaseNodeExecutor):
    type = "mergeobject"

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        Merge overrides into a source object (dict).

        The source dict comes from upstream via the 'source' input port.
        Overrides can come from:
          1. The 'overrides' input port (upstream dict, e.g. from ObjectBuilder)
          2. The 'overridesJson' config field (manual JSON text, e.g. '{"3010603": 3}')
        Port overrides take priority over config text.

        Output: merged dict (shallow merge, overrides win on key conflict)
        """
        # ── 1. Get source object ──────────────────────────────────────
        source = input_data.get('source')
        if source is None:
            # Fallback: treat the whole input_data (minus known control keys) as source
            _control_keys = {'source', 'overrides', 'overridesJson'}
            fallback = {k: v for k, v in input_data.items() if k not in _control_keys}
            source = fallback if fallback else {}

        # Unwrap Runtime Value marker if present
        if isinstance(source, dict) and '__value__' in source:
            source = source['__value__']

        # Smart extract: if source is a JSON executor result with 'jsonData', extract inner dict
        if isinstance(source, dict) and 'jsonData' in source and isinstance(source['jsonData'], dict):
            source = source['jsonData']

        if not isinstance(source, dict):
            return {"error": f"Source must be a dict, got {type(source).__name__}"}

        # ── 2. Get overrides ───────────────────────────────────────────
        overrides = input_data.get('overrides')
        overrides_from_port = isinstance(overrides, dict)

        # Unwrap Runtime Value marker if present
        if overrides_from_port and isinstance(overrides, dict) and '__value__' in overrides:
            overrides = overrides['__value__']
            overrides_from_port = isinstance(overrides, dict)

        # Config text fallback
        overrides_json_text = config.get('overridesJson', '').strip()
        overrides_from_config = {}
        if overrides_json_text:
            try:
                overrides_from_config = json.loads(overrides_json_text)
                if not isinstance(overrides_from_config, dict):
                    return {"error": f"overridesJson must be a JSON object, got {type(overrides_from_config).__name__}"}
            except json.JSONDecodeError as e:
                return {"error": f"overridesJson is not valid JSON: {e}"}

        # Port overrides win over config text; config fills gaps
        if overrides_from_port:
            final_overrides = {**overrides_from_config, **overrides}
        else:
            final_overrides = overrides_from_config

        # ── 3. Merge ───────────────────────────────────────────────────
        result = {**source, **final_overrides}

        return {
            "__runtime_type__": "object",
            "__value__": result,
            "result": result,
            "mergedKeys": list(final_overrides.keys()),
            "totalKeys": len(result),
        }
