import os
import re
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class LuaExecutor(BaseNodeExecutor):
    type = "lua"

    async def execute(self, config: dict, input_data: dict) -> dict:
        """
        Lua renderer: receives content from upstream node.
        - input_data['fileContent']: raw file content (string)
        - input_data['filePath']: original file path (optional)
        - config['entryFunction']: optional function name to extract
        """
        file_content = input_data.get("fileContent", "")
        file_path = input_data.get("filePath", "")

        entry_function = config.get("entryFunction", "")

        if not file_content:
            return {"error": "No input content. Connect an upstream node or provide content."}

        try:
            result = {"content": file_content, "filePath": file_path}

            if entry_function:
                pattern = rf'(?:function|local\s+function)\s+{re.escape(entry_function)}\s*\('
                match = re.search(pattern, file_content)
                if match:
                    start = match.start()
                    func_content = self._extract_function(file_content, start)
                    result["functionName"] = entry_function
                    result["functionContent"] = func_content
                else:
                    result["functionName"] = entry_function
                    result["functionContent"] = None
                    result["warning"] = f"Function '{entry_function}' not found"

            return result
        except Exception as e:
            return {"error": str(e)}

    def _extract_function(self, content: str, start: int) -> str:
        """Extract a Lua function body from the given start position."""
        lines = content[start:].split('\n')
        result = [lines[0]]
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith('end') and not stripped.startswith('end[') and not stripped.startswith('end.'):
                result.append(line)
                break
            result.append(line)
        return '\n'.join(result)
