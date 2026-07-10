import os
import json
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class JsonExecutor(BaseNodeExecutor):
    type = "json"

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        JSON renderer: receives content from upstream node.
        - input_data['fileContent']: raw file content (string) — from P4File or any node
        - input_data: full upstream output dict (used as fallback)
        - config['jsonPath']: optional JSON path expression to filter data
        """
        import logging
        logger = logging.getLogger(__name__)

        # Get content from upstream — fileContent port, or raw input_data
        file_content = input_data.get("fileContent", "")

        # jsonPath can come from config (manual input) or input_data (wired from upstream String node)
        json_path = config.get("jsonPath", "") or input_data.get("jsonPath", "")

        logger.warning(f"[JsonExecutor] input_data keys={list(input_data.keys())}, json_path={repr(json_path)}, file_content type={type(file_content)}, file_content[:80]={repr(str(file_content)[:80])}")

        # Strip the known control keys so they don't get treated as data in fallback
        _control_keys = {"fileContent", "jsonPath"}

        if not file_content and isinstance(input_data, dict):
            # If upstream output has no fileContent key, try remaining data fields as the source
            data_fields = {k: v for k, v in input_data.items() if k not in _control_keys}
            if data_fields:
                file_content = json.dumps(data_fields, ensure_ascii=False)

        if not file_content:
            return {"error": "No input content. Connect an upstream node or provide content."}

        try:
            # If upstream already gave us a parsed dict/list, use it directly
            if isinstance(file_content, (dict, list)):
                data = file_content
            else:
                data = json.loads(file_content)

            # If jsonPath is specified, filter the data
            if json_path:
                data = self._query_json_path(data, json_path)
                if data is None:
                    return {"error": f"JSON path '{json_path}' returned no results"}

            return {"jsonData": data}
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON content: {str(e)}"}
        except Exception as e:
            return {"error": str(e)}

    def _query_json_path(self, data, path: str):
        """Simple JSON path query: supports dot notation like $.data.items"""
        parts = path.lstrip("$").lstrip(".").split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                current = current[int(part)]
            else:
                return None
            if current is None:
                return None
        return current
