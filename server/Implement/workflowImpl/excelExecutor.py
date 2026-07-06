import os
import openpyxl
import config
from utility import p4Utils
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class ExcelExecutor(BaseNodeExecutor):
    type = "excel"

    async def execute(self, config: dict, input_data: dict) -> dict:
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
