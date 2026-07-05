import subprocess
import os
import json
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class JsonExecutor(BaseNodeExecutor):
    type = "json"

    async def execute(self, config: dict, input_data: dict) -> dict:
        p4_path = config.get("p4Path", "")
        json_path = config.get("jsonPath")

        if not p4_path:
            return {"error": "p4Path is required"}

        try:
            local_path = self._p4_sync(p4_path)
            with open(local_path, 'r', encoding='utf-8', errors='replace') as f:
                data = json.load(f)

            if json_path:
                data = self._query_json_path(data, json_path)

            return {"data": data, "path": json_path}
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

    def _query_json_path(self, data, path: str):
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
