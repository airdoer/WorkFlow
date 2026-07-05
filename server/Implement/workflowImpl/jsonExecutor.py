"""
JSON Node Executor - Fetch and parse JSON files from P4
"""
import subprocess
import os
import json
from typing import Dict, Any
from .nodeExecutor import BaseNodeExecutor


class JsonExecutor(BaseNodeExecutor):
    """Executor for JSON nodes"""
    
    @property
    def type(self) -> str:
        return "json"
    
    async def execute(self, config: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute JSON node
        
        Args:
            config: { p4Path: str, jsonPath?: str }
            input_data: Input from upstream nodes
            
        Returns:
            { data: Any, path?: str }
        """
        p4_path = config.get("p4Path")
        json_path = config.get("jsonPath")
        
        if not p4_path:
            raise ValueError("p4Path is required for JSON node")
        
        # Sync file from P4
        local_path = self._p4_sync(p4_path)
        
        # Read and parse JSON file
        try:
            with open(local_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            result = {"data": data}
            
            # Apply JSONPath filter if specified
            if json_path:
                filtered_data = self._apply_json_path(data, json_path)
                result["data"] = filtered_data
                result["path"] = json_path
            
            return result
            
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse JSON file: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Failed to read JSON file: {str(e)}")
    
    def _p4_sync(self, p4_path: str) -> str:
        """Sync file from P4 and return local path"""
        try:
            # Run p4 sync
            subprocess.run(
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
            parts = where_result.stdout.strip().split()
            if len(parts) >= 3:
                local_path = parts[2]
                if os.path.exists(local_path):
                    return local_path
            
            raise RuntimeError(f"Could not determine local path for {p4_path}")
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"P4 sync failed: {e.stderr}")
    
    def _apply_json_path(self, data: Any, json_path: str) -> Any:
        """
        Apply JSONPath filter to data
        
        Args:
            data: JSON data
            json_path: JSONPath expression (e.g., $.data.items)
            
        Returns:
            Filtered data
        """
        # Simple JSONPath implementation (supports basic dot notation)
        # For full JSONPath support, use jsonpath-ng library
        if json_path.startswith("$."):
            json_path = json_path[2:]  # Remove "$."
        
        parts = json_path.split(".")
        result = data
        
        for part in parts:
            if isinstance(result, dict):
                result = result.get(part)
            elif isinstance(result, list) and part.isdigit():
                index = int(part)
                if 0 <= index < len(result):
                    result = result[index]
                else:
                    return None
            else:
                return None
        
        return result
