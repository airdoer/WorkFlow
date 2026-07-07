import os
import json
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class JsonExecutor(BaseNodeExecutor):
    type = "json"

    async def execute(self, config: dict, input_data: dict) -> dict:
        """
        JSON renderer: receives content from upstream node.
        - input_data['fileContent']: raw file content (string) — from P4File or any node
        - input_data: full upstream output dict (used as fallback)
        - config['jsonPath']: optional JSON path expression to filter data
        """
        # Get content from upstream — fileContent port, or raw input_data
        file_content = input_data.get("fileContent", "")
        if not file_content and isinstance(input_data, dict):
            # If upstream output was a full dict without fileContent key,
            # try to use the whole dict as data
            if input_data:
                # Check if the entire input_data is the data to process
                # (e.g. from another JSON node or a prompt node)
                file_content = json.dumps(input_data, ensure_ascii=False)

        json_path = config.get("jsonPath", "")

        if not file_content:
            return {"error": "No input content. Connect an upstream node or provide content."}

        try:
            data = json.loads(file_content)

            # If jsonPath is specified, filter the data
            if json_path:
                data = self._query_json_path(data, json_path)
                if data is None:
                    return {"error": f"JSON path '{json_path}' returned no results"}

            return {"data": data, "path": json_path or None}
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
