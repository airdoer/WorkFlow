"""
Excel Node Executor - Fetch and parse Excel files from P4
"""
import subprocess
import os
from typing import Dict, Any
from .nodeExecutor import BaseNodeExecutor


class ExcelExecutor(BaseNodeExecutor):
    """Executor for Excel nodes"""
    
    @property
    def type(self) -> str:
        return "excel"
    
    async def execute(self, config: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Excel node
        
        Args:
            config: { p4Path: str, sheet?: str }
            input_data: Input from upstream nodes
            
        Returns:
            { columns: List[str], rows: List[Dict] }
        """
        p4_path = config.get("p4Path")
        sheet_name = config.get("sheet")
        
        if not p4_path:
            raise ValueError("p4Path is required for Excel node")
        
        # Sync file from P4
        local_path = self._p4_sync(p4_path)
        
        # Parse Excel file
        try:
            import openpyxl
            wb = openpyxl.load_workbook(local_path, data_only=True)
            ws = wb[sheet_name] if sheet_name else wb.active
            
            # Extract columns (first row)
            columns = [cell.value for cell in ws[1]]
            
            # Extract data rows
            rows = []
            for row in ws.iter_rows(min_row=2, values_only=True):
                row_dict = dict(zip(columns, row))
                rows.append(row_dict)
            
            return {
                "columns": columns,
                "rows": rows
            }
        except ImportError:
            raise RuntimeError("openpyxl is not installed. Please install it with: pip install openpyxl")
        except Exception as e:
            raise RuntimeError(f"Failed to parse Excel file: {str(e)}")
    
    def _p4_sync(self, p4_path: str) -> str:
        """
        Sync file from P4 and return local path
        
        Args:
            p4_path: P4 depot path (e.g., //C7/Development/Mainline/Server/Data/Excel/file.xlsx)
            
        Returns:
            Local file path
        """
        try:
            # Run p4 sync
            result = subprocess.run(
                ["p4", "sync", p4_path],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Get local path with p4 where
            where_result = subprocess.run(
                ["p4", "where", p4_path],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse local path from "p4 where" output
            # Format: "depot_path //client/path /local/path"
            parts = where_result.stdout.strip().split()
            if len(parts) >= 3:
                local_path = parts[2]
                if os.path.exists(local_path):
                    return local_path
            
            raise RuntimeError(f"Could not determine local path for {p4_path}")
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"P4 sync failed: {e.stderr}")
