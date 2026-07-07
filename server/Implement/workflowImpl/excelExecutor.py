import os
import json
import openpyxl
import io
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class ExcelExecutor(BaseNodeExecutor):
    type = "excel"

    async def execute(self, config: dict, input_data: dict) -> dict:
        """
        Excel renderer: receives content from upstream node.
        - input_data['localPath']: local file path (from P4File node for binary files)
        - input_data['fileContent']: raw content (for CSV or text-based)
        - input_data['fileType']: file type hint from upstream
        - config['sheet']: optional sheet name
        - config['rowFilter']: optional list of row indices (1-based)
        - config['columnFilter']: optional list of column names
        """
        local_path = input_data.get("localPath", "")
        file_content = input_data.get("fileContent", "")
        file_type = input_data.get("fileType", "")

        sheet_name = config.get("sheet", "")
        row_filter = config.get("rowFilter")  # list of row numbers (1-based strings)
        column_filter = config.get("columnFilter")  # list of column names

        # Validate content format — reject JSON input for Excel
        if file_type == "json" or (not local_path and file_content and not file_content.startswith("PK")):
            try:
                json.loads(file_content[:500] if file_content else "{}")
                return {"error": "Input content is JSON format, not Excel. Use the JSON node instead."}
            except (json.JSONDecodeError, ValueError):
                pass

        if not local_path and not file_content:
            return {"error": "No input content. Connect an upstream node or provide content."}

        try:
            # Use local path if available (from P4File node for xlsx files)
            if local_path and os.path.exists(local_path):
                wb = openpyxl.load_workbook(local_path, data_only=True)
            elif file_content:
                # Try to load from content bytes (for xlsx binary)
                try:
                    wb = openpyxl.load_workbook(
                        io.BytesIO(file_content.encode('latin-1') if isinstance(file_content, str) else file_content),
                        data_only=True,
                    )
                except Exception:
                    # Try CSV parsing
                    return self._parse_csv(file_content, row_filter, column_filter)
            else:
                return {"error": "Cannot open file. Ensure an upstream P4 File node is connected with an Excel file."}

            # Select sheet
            if sheet_name:
                if sheet_name not in wb.sheetnames:
                    return {"error": f"Sheet '{sheet_name}' not found. Available: {', '.join(wb.sheetnames)}"}
                ws = wb[sheet_name]
            else:
                ws = wb.active

            # Extract all data — replace None column headers with empty string
            raw_columns = [cell.value for cell in ws[1]]
            columns = [str(c) if c is not None else f"Col{i+1}" for i, c in enumerate(raw_columns)]
            rows = []
            for row in ws.iter_rows(min_row=2, values_only=True):
                rows.append(dict(zip(columns, row)))

            # Apply row filter
            if row_filter and len(row_filter) > 0:
                row_indices = [int(r) - 1 for r in row_filter if r.isdigit() and int(r) <= len(rows)]
                rows = [rows[i] for i in row_indices if 0 <= i < len(rows)]

            # Apply column filter — use set for safe membership test
            if column_filter and len(column_filter) > 0:
                column_set = set(column_filter)
                columns = [c for c in columns if c in column_set]
                rows = [{k: v for k, v in row.items() if k in column_set} for row in rows]

            return {"columns": columns, "rows": rows, "sheetNames": wb.sheetnames}
        except Exception as e:
            return {"error": str(e)}

    def _parse_csv(self, content: str, row_filter, column_filter) -> dict:
        """Parse CSV content as a fallback."""
        import csv
        reader = csv.DictReader(io.StringIO(content))
        columns = reader.fieldnames or []
        rows = list(reader)

        if row_filter and len(row_filter) > 0:
            row_indices = [int(r) - 1 for r in row_filter if r.isdigit() and int(r) <= len(rows)]
            rows = [rows[i] for i in row_indices if 0 <= i < len(rows)]

        if column_filter and len(column_filter) > 0:
            column_set = set(column_filter)
            columns = [c for c in columns if c in column_set]
            rows = [{k: v for k, v in row.items() if k in column_set} for row in rows]

        return {"columns": columns, "rows": rows}
