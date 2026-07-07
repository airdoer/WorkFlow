import os
import json
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class JsonExecutor(BaseNodeExecutor):
    type = "json"

    async def execute(self, config: dict, input_data: dict) -> dict:
        """
        JSON renderer: receives file content from upstream P4File node.
        - input_data['fileContent']: raw file content (string)
        - input_data['filePath']: original P4 path
        - config['jsonPath']: optional JSON path expression to filter data
        """
        file_content = input_data.get("fileContent", "")
        p4_path = input_data.get("filePath", "")
        file_type = input_data.get("fileType", "")

        json_path = config.get("jsonPath")

        if not file_content:
            return {"error": "No file content provided. Connect a P4 File node to this JSON renderer."}

        try:
            data = json.loads(file_content)

            if json_path:
                data = self._query_json_path(data, json_path)

            return {"data": data, "path": json_path, "filePath": p4_path}
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON: {str(e)}"}
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
