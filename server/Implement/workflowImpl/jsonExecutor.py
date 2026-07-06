import os
import json
import config
from utility import p4Utils
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
        """
        使用 p4Utils.download_file 将文件同步到本地 P4_WORKSPACE_DIRECTORY。
        不依赖 p4 client root，直接用 p4 print 下载到指定路径。
        """
        # 规范化 p4 路径，移除多余的斜杠
        p4_path = p4Utils.normalize_p4_path(p4_path)

        # 构建 local 路径：P4_WORKSPACE_DIRECTORY + depot 相对路径
        # 例如: //C7/Development/Mainline/Server/config/production/c7_video.json
        #   -> /app/p4WorkSpace/C7/Development/Mainline/Server/config/production/c7_video.json
        relative_path = p4_path.lstrip("/").replace("//", "")
        local_path = os.path.join(config.P4_WORKSPACE_DIRECTORY, relative_path)

        # 使用 p4Utils 下载（会自动创建目录，支持版本号）
        success = p4Utils.update_file(p4_path, local_path, force=True)
        if not success:
            raise RuntimeError(f"Failed to sync P4 file: {p4_path}")

        return local_path

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
