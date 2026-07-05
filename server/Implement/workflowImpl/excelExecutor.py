import subprocess
import os
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor
from utility import p4Utils


class ExcelExecutor(BaseNodeExecutor):
    type = "excel"

    async def execute(self, config: dict, input_data: dict) -> dict:
        import openpyxl

        p4_path = config.get("p4Path", "")
        sheet_name = config.get("sheet")

        if not p4_path:
            return {"error": "p4Path is required"}

        try:
            local_path = self._p4_sync(p4_path)
            wb = openpyxl.load_workbook(local_path, data_only=True)
            ws = wb[sheet_name] if sheet_name else wb.active

            columns = [cell.value for cell in ws[1]]
            rows = []
            for row in ws.iter_rows(min_row=2, values_only=True):
                rows.append(dict(zip(columns, row)))

            return {"columns": columns, "rows": rows}
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
