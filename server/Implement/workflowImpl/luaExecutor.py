"""
Lua Node Executor - Fetch Lua files from P4
"""
import subprocess
import os
import re
from typing import Dict, Any
from .nodeExecutor import BaseNodeExecutor


class LuaExecutor(BaseNodeExecutor):
    """Executor for Lua nodes"""
    
    @property
    def type(self) -> str:
        return "lua"
    
    async def execute(self, config: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Lua node
        
        Args:
            config: { p4Path: str, entryFunction?: str }
            input_data: Input from upstream nodes
            
        Returns:
            { content: str, functionName?: str, functionContent?: str }
        """
        p4_path = config.get("p4Path")
        entry_function = config.get("entryFunction")
        
        if not p4_path:
            raise ValueError("p4Path is required for Lua node")
        
        # Sync file from P4
        local_path = self._p4_sync(p4_path)
        
        # Read Lua file content
        try:
            with open(local_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            result = {"content": content}
            
            # Extract specific function if requested
            if entry_function:
                function_content = self._extract_function(content, entry_function)
                if function_content:
                    result["functionName"] = entry_function
                    result["functionContent"] = function_content
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"Failed to read Lua file: {str(e)}")
    
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
    
    def _extract_function(self, content: str, function_name: str) -> str:
        """
        Extract a specific function from Lua content
        
        Args:
            content: Full Lua file content
            function_name: Name of the function to extract
            
        Returns:
            Function content or empty string if not found
        """
        # Simple regex to match Lua function definition
        # Matches: function functionName(...) ... end
        pattern = rf'function\s+{re.escape(function_name)}\s*\([^)]*\).*?end'
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            return match.group(0)
        
        # Try local function pattern
        pattern = rf'local\s+function\s+{re.escape(function_name)}\s*\([^)]*\).*?end'
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            return match.group(0)
        
        return ""
