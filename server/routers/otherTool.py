# 和游戏服务器 战斗相关的route放这个里 这里只放对内的接口 对外的放battleExternal里

# builtin
from datetime import datetime
import os
import uuid
import subprocess
import re

# 3rd ext
from flask import render_template, request, jsonify, Response
from sqlalchemy import and_
import io
import csv

# int
from appImp import app
from Implement.hotfixImpl import p4Imp
from Implement.hotfixImpl import hotfixImp
from utility import p4Utils
import config
import json
from managers.timeMgr import cron
from Implement.hotfixImpl import luaParserImp
# region init

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

    def _is_word_start(ch: str) -> bool:
        return ('a' <= ch <= 'z') or ('A' <= ch <= 'Z') or ch == '_'

    def _is_word_part(ch: str) -> bool:
        return _is_word_start(ch) or ('0' <= ch <= '9')

    def _tokenize_lua_like(src: str):
        tokens = []
        i = 0
        n = len(src)
        while i < n:
            ch = src[i]
            if ch == ' ' or ch == '\t':
                i += 1
                continue

            if ch == "'" or ch == '"':
                q = ch
                j = i + 1
                esc = False
                while j < n:
                    c = src[j]
                    if esc:
                        esc = False
                        j += 1
                        continue
                    if c == '\\':
                        esc = True
                        j += 1
                        continue
                    if c == q:
                        j += 1
                        break
                    j += 1
                tokens.append(('string', src[i:j]))
                i = j
                continue

            if _is_word_start(ch):
                j = i + 1
                while j < n and _is_word_part(src[j]):
                    j += 1
                tokens.append(('word', src[i:j]))
                i = j
                continue

            if '0' <= ch <= '9':
                j = i + 1
                while j < n and (('0' <= src[j] <= '9') or src[j] == '.' or ('a' <= src[j].lower() <= 'f') or src[j].lower() == 'x'):
                    j += 1
                tokens.append(('number', src[i:j]))
                i = j
                continue

            if i + 3 <= n and src[i:i+3] == '...':
                tokens.append(('op', '...'))
                i += 3
                continue
            if i + 2 <= n:
                two = src[i:i+2]
                if two in ('..', '==', '~=', '<=', '>=', '::', '--'):
                    tokens.append(('op', two))
                    i += 2
                    continue

            tokens.append(('op', ch))
            i += 1

        return tokens

    def _should_preserve_newlines(src_lines: list) -> bool:
        if len(src_lines) <= 1:
            return False
        joined_text = '\n'.join(src_lines)
        tokens = _tokenize_lua_like(joined_text)
        if not tokens:
            return False
        block_keywords = {
            'function', 'for', 'while', 'repeat', 'until', 'if', 'then', 'do', 'end', 'elseif', 'else'
        }
        for t, v in tokens:
            if t == 'word' and v in block_keywords:
                return True
        return False

    def _needs_space(prev, nxt) -> bool:
        pt, pv = prev
        nt, nv = nxt
        if pv == '-' and nv == '-':
            return True
        if pt in ('word', 'number') and nt in ('word', 'number'):
            return True
        return False

    def _compact_single_line(src: str) -> str:
        src = src.strip()
        if not src:
            return ''
        tokens = _tokenize_lua_like(src)
        if not tokens:
            return ''
        out = [tokens[0][1]]
        for idx in range(1, len(tokens)):
            if _needs_space(tokens[idx - 1], tokens[idx]):
                out.append(' ')
            out.append(tokens[idx][1])
        return ''.join(out)

    compacted_lines = [_compact_single_line(line) for line in lines]
    compacted_lines = [line for line in compacted_lines if line]
    if not compacted_lines:
        return ''

    if _should_preserve_newlines(lines):
        return '\n'.join(compacted_lines)

    return ';'.join(compacted_lines).strip(';')

class LuaSyntaxCheckError(Exception):
    def __init__(self, stage: str, errors: list):
        self.stage = stage
        self.errors = errors or []
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        if not self.errors:
            return 'Lua syntax errors'
        first = self.errors[0]
        line = first.get('line')
        column = first.get('column')
        msg = first.get('message') or ''
        return f"Lua语法错误({self.stage}): line {line}:{column} {msg}".strip()


def _collect_lua_syntax_errors(code: str) -> list:
    from antlr4 import InputStream, CommonTokenStream, Token
    from antlr4.error.ErrorListener import ErrorListener
    from luaparser.parser.LuaLexer import LuaLexer
    from luaparser.parser.LuaParser import LuaParser

    class _Listener(ErrorListener):
        def __init__(self):
            super().__init__()
            self.errors = []

        def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
            offending = None
            try:
                offending = getattr(offendingSymbol, 'text', None)
            except Exception:
                offending = None
            self.errors.append({
                'line': line,
                'column': column,
                'message': msg,
                'offending': offending
            })

    lexer = LuaLexer(InputStream(code))
    lexer.removeErrorListeners()
    lexer_listener = _Listener()
    lexer.addErrorListener(lexer_listener)

    token_stream = CommonTokenStream(lexer, channel=Token.DEFAULT_CHANNEL)
    parser = LuaParser(token_stream)
    parser.removeErrorListeners()
    parser_listener = _Listener()
    parser.addErrorListener(parser_listener)

    parser.start_()

    errors = []
    errors.extend(lexer_listener.errors)
    errors.extend(parser_listener.errors)
    return errors


def _check_lua_syntax(stage: str, code: str):
    errors = _collect_lua_syntax_errors(code)
    if errors:
        raise LuaSyntaxCheckError(stage, errors)
    luaParserImp.ast.parse(code)


def _normalize_command_for_parse(text: str) -> str:
    s = '' if text is None else str(text)
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    return s.strip()

@app.route('/serverCommandGenerate', methods=['GET', 'POST'])
def serverCommandGenerate():
    app.logger.info("czx serverCommandGenerate")
    
    try:
        if request.method == 'GET':
            command = request.args.get('command', '')
            broadcast_raw = request.args.get('broadcast', '1')
        else:
            data = request.get_json(silent=True) or {}
            command = data.get('command', '')
            broadcast_raw = data.get('broadcast', True)

        if not command or not str(command).strip():
            return jsonify({'code': 1, 'errMsg': 'command 不能为空'})

        def _to_bool(val, default=True):
            if isinstance(val, bool):
                return val
            if val is None:
                return default
            s = str(val).strip().lower()
            if s in ('1', 'true', 'yes', 'y', 'on'):
                return True
            if s in ('0', 'false', 'no', 'n', 'off'):
                return False
            return default

        broadcast = _to_bool(broadcast_raw, default=True)

        normalized_for_parse = _normalize_command_for_parse(command)
        _check_lua_syntax('original', normalized_for_parse)

        compacted = _compact_command(command)
        _check_lua_syntax('compacted', compacted)
        if broadcast:
            quoted = _quote_js_string(compacted)
            result = f"broadcastCommand({quoted})"
        else:
            result = compacted
        
        return jsonify({
            'code': 0,
            'errMsg': '',
            'result': result,
            'broadcast': broadcast
        })
        
    except LuaSyntaxCheckError as e:
        app.logger.error(f"czx serverCommandGenerate syntax error: {e}", exc_info=True)
        return jsonify({'code': 1, 'errMsg': str(e), 'errDetail': e.errors, 'stage': e.stage})
    except Exception as e:
        app.logger.error(f"czx serverCommandGenerate failed: {e}", exc_info=True)
        return jsonify({'code': 1, 'errMsg': str(e)})
