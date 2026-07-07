import os
import json
import openpyxl
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class ExcelExecutor(BaseNodeExecutor):
    type = "excel"

    async def execute(self, config: dict, input_data: dict) -> dict:
        """
        Excel renderer: receives file content from upstream P4File node.
        - input_data['fileContent'] or input_data['localPath']: raw file content or local path
        - input_data['filePath']: original P4 path
        - config['sheet']: optional sheet name
        - config['rowFilter']: optional list of row indices (1-based)
        - config['columnFilter']: optional list of column names
        """
        # Get file path from upstream P4File node
        local_path = input_data.get("localPath", "")
        p4_path = input_data.get("filePath", "")
        file_type = input_data.get("fileType", "")
        file_content = input_data.get("fileContent", "")

        sheet_name = config.get("sheet")
        row_filter = config.get("rowFilter")  # list of row numbers (1-based strings)
        column_filter = config.get("columnFilter")  # list of column names

        if not local_path and not file_content:
            return {"error": "No file content provided. Connect a P4 File node to this Excel renderer."}

        try:
            # Use local path if available (from P4File node), otherwise try to read content
            if local_path and os.path.exists(local_path):
                wb = openpyxl.load_workbook(local_path, data_only=True)
            else:
                # If we only have raw content, we can't parse Excel binary directly
                return {"error": "Excel requires a local file path. Ensure P4 File node is connected."}

            # Select sheet
            if sheet_name:
                if sheet_name not in wb.sheetnames:
                    return {"error": f"Sheet '{sheet_name}' not found. Available: {', '.join(wb.sheetnames)}"}
                ws = wb[sheet_name]
            else:
                ws = wb.active

            # Extract all data
            columns = [cell.value for cell in ws[1]]
            rows = []
            for row in ws.iter_rows(min_row=2, values_only=True):
                rows.append(dict(zip(columns, row)))

            # Apply row filter
            if row_filter and len(row_filter) > 0:
                row_indices = [int(r) - 1 for r in row_filter if r.isdigit() and int(r) <= len(rows)]
                rows = [rows[i] for i in row_indices if 0 <= i < len(rows)]

            # Apply column filter
            if column_filter and len(column_filter) > 0:
                filtered_columns = [c for c in columns if c in column_filter]
                rows = [{k: v for k, v in row.items() if k in column_filter} for row in rows]
                columns = filtered_columns

            return {"columns": columns, "rows": rows, "sheetNames": wb.sheetnames, "filePath": p4_path}
        except Exception as e:
            return {"error": str(e)}
