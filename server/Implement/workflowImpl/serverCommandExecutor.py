"""
ServerCommand (服务端指令) 节点执行器 — 对 Lua 代码做语法检查 + 压缩，
根据 broadcast 标志生成 broadcastCommand(...) 或直接输出压缩后的代码。

逻辑移植自 game-watchman/server/routers/otherTool.py:serverCommandGenerate
"""
import json
import logging
import subprocess
import re
import os

from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)

# ── Lua 语法检查 / 压缩 / 引号转义 ────────────────────────────────────

def _quote_js_string(s: str) -> str:
    s = '' if s is None else str(s)
    has_single = "'" in s
    has_double = '"' in s
    outer = "'"
    if has_single and not has_double:
        outer = '"'
    elif has_double and not has_single:
        outer = "'"
    elif has_single and has_double:
        outer = '"'
    normalized = s.replace('\r\n', '\n')
    if outer == '"':
        escaped = normalized.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        return f'"{escaped}"'
    escaped = normalized.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
    return f"'{escaped}'"


def _compact_command(text: str) -> str:
    s = '' if text is None else str(text)
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    lines = [line.strip() for line in s.split('\n')]
    lines = [line for line in lines if line]
    if not lines:
        return ''
    # Simple compact: join with semicolons, strip trailing ;
    compacted = ';'.join(lines).strip(';')
    return compacted


def _check_lua_syntax_via_ast(code: str):
    """Attempt Lua syntax check using the luaparser AST (if available)."""
    try:
        from luaparser import ast
        ast.parse(code)
        return []
    except Exception as e:
        return [{'line': 0, 'column': 0, 'message': str(e)}]


class ServerCommandExecutor(BaseNodeExecutor):
    type = "servercommand"

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        ServerCommand 节点执行：
        1. 获取 command（Lua 代码）和 broadcast 标志
        2. 语法检查
        3. 压缩代码
        4. 根据 broadcast 生成 broadcastCommand(...) 或直接输出

        config 字段：
        - command: Lua 代码（必填）
        - broadcast: 是否广播（默认 true）
        """
        # 获取参数：config 优先，input_data 次之
        command = config.get('command', '') or input_data.get('command', '')
        broadcast_raw = config.get('broadcast', 'true')

        if not command or not str(command).strip():
            return {"success": False, "error": "command 不能为空（请输入 Lua 指令）"}

        # Parse broadcast flag
        broadcast = str(broadcast_raw).strip().lower() in ('true', '1', 'yes')
        normalized = command.replace('\r\n', '\n').strip()

        # Syntax check
        syntax_errors = _check_lua_syntax_via_ast(normalized)
        if syntax_errors:
            first = syntax_errors[0]
            err_msg = f"Lua语法错误: line {first.get('line', '?')}:{first.get('column', '?')} {first.get('message', '')}"
            return {"success": False, "error": err_msg}

        # Compact
        compacted = _compact_command(command)

        # Syntax check on compacted version too
        if compacted:
            syntax_errors2 = _check_lua_syntax_via_ast(compacted)
            if syntax_errors2:
                return {"success": False, "error": f"压缩后语法错误: {syntax_errors2[0].get('message', '')}"}

        # Generate result
        if broadcast:
            quoted = _quote_js_string(compacted)
            result = f"broadcastCommand({quoted})"
        else:
            result = compacted

        return {
            "success": True,
            "result": result,
            "broadcast": broadcast,
        }
