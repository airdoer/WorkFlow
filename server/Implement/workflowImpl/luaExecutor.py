import subprocess
import os
import re
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
        result = subprocess.run(
            ["p4", "sync", p4_path],
            capture_output=True, text=True,
            env={**os.environ, "P4CONFIG": "/app/p4/.p4config"},
        )
        if result.returncode != 0:
            raise RuntimeError(f"P4 sync failed: {result.stderr}")
        client_root = self._get_client_root()
        relative_path = p4_path.lstrip("/").replace("/", os.sep, 1)
        return os.path.join(client_root, relative_path)

    def _get_client_root(self) -> str:
        result = subprocess.run(
            ["p4", "info"],
            capture_output=True, text=True,
            env={**os.environ, "P4CONFIG": "/app/p4/.p4config"},
        )
        for line in result.stdout.splitlines():
            if line.startswith("Client root:"):
                return line.split(":", 1)[1].strip()
        return "/app/p4WorkSpace"

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
