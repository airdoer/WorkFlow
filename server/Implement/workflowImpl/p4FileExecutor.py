import os
import json
import config
from utility import p4Utils
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class P4FileExecutor(BaseNodeExecutor):
    type = "p4file"

    async def execute(self, config: dict, input_data: dict) -> dict:
        p4_path = config.get("p4Path", "")

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
        import subprocess as _sp
        import os as _os

        p4_path = p4Utils.normalize_p4_path(p4_path)
        relative_path = p4_path.lstrip("/").replace("//", "")
        local_path = _os.path.join(config.P4_WORKSPACE_DIRECTORY, relative_path)

        # Debug: test p4 connectivity inline
        test_result = _sp.run(
            ["p4", "files", p4_path.split("#")[0]],
            stdout=_sp.PIPE, stderr=_sp.PIPE, check=False
        )
        test_out = test_result.stdout.decode("utf-8", errors="ignore").strip()
        test_err = test_result.stderr.decode("utf-8", errors="ignore").strip()

        if not test_out:
            raise RuntimeError(
                f"P4 check failed for {p4_path}: stdout={test_out!r} stderr={test_err!r} "
                f"returncode={test_result.returncode} cwd={_os.getcwd()!r} "
                f"P4CONFIG={_os.environ.get('P4CONFIG','NOT_SET')!r}"
            )

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
