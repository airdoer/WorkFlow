import os
import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)


class FileExecutor(BaseNodeExecutor):
    """File node: read local file content."""

    type = "file"

    def execute(self, config: dict, input_data: dict) -> dict:
        file_path = input_data.get("path", config.get("path", ""))
        encoding = config.get("encoding", "utf-8")

        if not file_path:
            return {"error": "File path is required"}

        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}

        try:
            file_size = os.path.getsize(file_path)
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                content = f.read()

            # Detect file type
            ext = os.path.splitext(file_path)[1].lower()
            file_type = {
                '.json': 'json',
                '.xlsx': 'excel',
                '.xls': 'excel',
                '.csv': 'csv',
                '.lua': 'lua',
                '.py': 'python',
                '.xml': 'xml',
                '.yaml': 'yaml',
                '.yml': 'yaml',
                '.txt': 'text',
                '.md': 'markdown',
            }.get(ext, 'text')

            return {
                "__runtime_type__": "string",
                "__value__": content,
                "content": content,
                "filePath": file_path,
                "fileType": file_type,
                "size": file_size,
                "localPath": file_path,
            }

        except Exception as e:
            logger.exception("[File] Error reading '%s': %s", file_path, e)
            return {"error": f"Failed to read file: {e}"}
