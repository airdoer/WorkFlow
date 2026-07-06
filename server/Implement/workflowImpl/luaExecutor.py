import os
import re
import config
from utility import p4Utils
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class LuaExecutor(BaseNodeExecutor):
    type = "lua"

    async def execute(self, config: dict, input_data: dict) -> dict:
        p4_path = config.get("p4Path", "")
        entry_function = config.get("entryFunction")

        if not p4_path:
            return {"error": "p4Path is required"}

        try:
            local_path = self._p4_sync(p4_path)
            with open(local_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            result = {"content": content}

            if entry_function:
                pattern = rf'(?:function|local\s+function)\s+{re.escape(entry_function)}\s*\('
                match = re.search(pattern, content)
                if match:
                    start = match.start()
                    func_content = self._extract_function(content, start)
                    result["functionName"] = entry_function
                    result["functionContent"] = func_content

            return result
        except Exception as e:
            return {"error": str(e)}

    def _p4_sync(self, p4_path: str) -> str:
        """
        使用 p4Utils.download_file 将文件同步到本地 P4_WORKSPACE_DIRECTORY。
        不依赖 p4 client root，直接用 p4 print 下载到指定路径。
        """
        p4_path = p4Utils.normalize_p4_path(p4_path)
        relative_path = p4_path.lstrip("/").replace("//", "")
        local_path = os.path.join(config.P4_WORKSPACE_DIRECTORY, relative_path)

        success = p4Utils.update_file(p4_path, local_path, force=True)
        if not success:
            raise RuntimeError(f"Failed to sync P4 file: {p4_path}")

        return local_path

    def _extract_function(self, content: str, start: int) -> str:
        depth = 0
        i = start
        while i < len(content):
            if content[i] == '{' or (content[i:i+6] == 'function' and depth == 0):
                pass
            i += 1
        lines = content[start:].split('\n')
        result = [lines[0]]
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith('end') and not stripped.startswith('end[') and not stripped.startswith('end.'):
                result.append(line)
                break
            result.append(line)
        return '\n'.join(result)
