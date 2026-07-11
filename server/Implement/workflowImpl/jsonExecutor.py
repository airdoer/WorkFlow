import re
import json
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class JsonExecutor(BaseNodeExecutor):
    type = "json"

    def execute(self, config: dict, input_data: dict) -> dict:
        import logging
        logger = logging.getLogger(__name__)

        # Get content from upstream — fileContent port, jsonStr port, or fallback to whole input
        file_content = input_data.get("fileContent", "") or input_data.get("jsonStr", "")

        # jsonPath can come from config (manual) or wired input_data
        json_path = config.get("jsonPath", "") or input_data.get("jsonPath", "")

        logger.warning(
            "[JsonExecutor] input_data keys=%s, json_path=%r, "
            "file_content type=%s, file_content[:80]=%r",
            list(input_data.keys()), json_path, type(file_content), str(file_content)[:80],
        )

        _control_keys = {"fileContent", "jsonPath", "jsonStr"}

        if not file_content and isinstance(input_data, dict):
            data_fields = {k: v for k, v in input_data.items() if k not in _control_keys}
            if data_fields:
                file_content = json.dumps(data_fields, ensure_ascii=False)

        if not file_content:
            return {"error": "No input content. Connect an upstream node or provide content."}

        try:
            if isinstance(file_content, (dict, list)):
                data = file_content
            else:
                try:
                    data = json.loads(file_content)
                    # Double-encoded JSON string → decode again
                    if isinstance(data, str):
                        try:
                            data = json.loads(data)
                        except Exception:
                            pass
                except json.JSONDecodeError as e:
                    return {"error": f"Invalid JSON content: {str(e)}"}

            if json_path:
                data = self._query_json_path(data, json_path)
                if data is None:
                    return {"error": f"JSON path '{json_path}' returned no results"}

            return {
                "jsonData": data,
                "jsonStr": data if isinstance(data, str) else json.dumps(data, ensure_ascii=False),
            }
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON content: {str(e)}"}
        except Exception as e:
            return {"error": str(e)}

    def _query_json_path(self, data, path: str):
        """JSON path query supporting dot notation and array indexing.

        Examples:
            serverHotfixInfo          -> dict key
            serverHotfixInfo[0]       -> first element
            serverHotfixInfo[-1]      -> last element
            data.list[2].name         -> mixed
            items[0][1]               -> nested indexes
        """
        path = path.strip().lstrip("$").lstrip(".")

        # Split on dots that are NOT inside brackets
        tokens = [seg for seg in re.split(r"\.(?![^\[]*\])", path) if seg]

        current = data
        for token in tokens:
            if current is None:
                return None
            # Split token into key part and bracket-index part(s)
            m = re.fullmatch(r"([^\[]*)((?:\[-?\d+\])*)", token)
            if not m:
                return None
            key_part, index_part = m.group(1), m.group(2)

            if key_part:
                if isinstance(current, dict):
                    current = current.get(key_part)
                else:
                    return None

            if index_part:
                for idx_str in re.findall(r"\[(-?\d+)\]", index_part):
                    if isinstance(current, list):
                        try:
                            current = current[int(idx_str)]
                        except IndexError:
                            return None
                    else:
                        return None

        return current
