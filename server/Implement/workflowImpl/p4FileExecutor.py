import os
import json
import config
from utility import p4Utils
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class P4FileExecutor(BaseNodeExecutor):
    type = "p4file"

    def execute(self, config: dict, input_data: dict) -> dict:
        # 连线输入优先，其次 config（支持从 String 节点连线提供路径）
        p4_path = input_data.get('p4Path') or config.get('p4Path', '')

        if not p4_path:
            return {"error": "p4Path is required"}

        try:
            local_path = self._p4_sync(p4_path)

            # Read file content
            with open(local_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            # Try to parse as JSON for structured output
            try:
                json_data = json.loads(content)
                file_type = "json"
            except (json.JSONDecodeError, ValueError):
                file_type = self._detect_file_type(p4_path, content)

            return {
                "filePath": p4_path,
                "localPath": local_path,
                "fileType": file_type,
                "fileContent": content,
                "size": os.path.getsize(local_path),
            }
        except Exception as e:
            return {"error": str(e)}

    def _p4_sync(self, p4_path: str) -> str:
        """
        Sync P4 file to local workspace using p4Utils.
        """
        p4_path = p4Utils.normalize_p4_path(p4_path)
        relative_path = p4_path.lstrip("/").replace("//", "")
        local_path = os.path.join(config.P4_WORKSPACE_DIRECTORY, relative_path)

        success = p4Utils.update_file(p4_path, local_path, force=True)
        if not success:
            raise RuntimeError(f"Failed to sync P4 file: {p4_path}")

        return local_path

    def _detect_file_type(self, p4_path: str, content: str) -> str:
        """Detect file type from extension or content."""
        ext = p4_path.rsplit(".", 1)[-1].lower() if "." in p4_path else ""
        type_map = {
            "xlsx": "excel", "xls": "excel", "csv": "excel",
            "lua": "lua",
            "json": "json",
            "xml": "xml",
            "yaml": "yaml", "yml": "yaml",
            "py": "python",
            "txt": "text",
            "md": "markdown",
        }
        return type_map.get(ext, "text")
