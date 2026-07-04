# -*- coding: utf-8 -*-
"""
Hotfix lua 文件函数名提取模块
------------------------------
Layer 1: AST 遍历（luaParserImp.extract_func_names）
Layer 2: 局部变量常量传播（解析 HotfixComponentFunction 动态参数）
Layer 3: AI fallback（对 unresolved_calls 用 LLM 补充推断）
Layer 4: 正则 fallback（AST 整体失败时兜底）
"""

import re
import json
import logging
import os
import urllib.request

logger = logging.getLogger(__name__)


# ── AI Proxy URL ──────────────────────────────────────────────────────────

def _get_proxy_host():
    """自动探测 AI Proxy 地址：容器内用网关 IP，宿主机用 127.0.0.1"""
    if not os.path.exists('/.dockerenv'):
        return '127.0.0.1'
    try:
        import socket
        socket.getaddrinfo('host.docker.internal', 19999)
        return 'host.docker.internal'
    except socket.gaierror:
        pass
    try:
        with open('/proc/net/route') as f:
            for line in f:
                fields = line.strip().split()
                if len(fields) >= 3 and fields[1] == '00000000':
                    gw_hex = fields[2]
                    if gw_hex != '00000000':
                        gw_bytes = [int(gw_hex[i:i+2], 16) for i in range(6, -1, -2)]
                        return f'{gw_bytes[0]}.{gw_bytes[1]}.{gw_bytes[2]}.{gw_bytes[3]}'
    except Exception:
        pass
    return '172.17.0.1'


_FLICKCLI_PROXY_HOST = _get_proxy_host()
_FLICKCLI_PROXY_URL = f'http://{_FLICKCLI_PROXY_HOST}:19999'


# ── 正则 fallback ─────────────────────────────────────────────────────────

_FUNC_MOD_RE = re.compile(r'^([\w.]+)\.(\w+)\s*=\s*function\s*\(')


def _regex_extract(lua_content):
    """最后兜底：单模式正则提取函数名"""
    func_names = []
    for line in lua_content.strip().split('\n'):
        stripped = line.strip()
        if stripped.startswith('--') or stripped.startswith('print'):
            continue
        m = _FUNC_MOD_RE.match(stripped)
        if m:
            func_names.append(f"{m.group(1)}.{m.group(2)}")
    return func_names


# ── AI fallback ───────────────────────────────────────────────────────────

def extract_func_names_with_ai_fallback(lua_content, file_name='unknown', ext_logger=None):
    """
    对 unresolved_calls（无法静态解析的动态写法）用 AI 补充识别。

    适用场景：HotfixComponentFunction(componentName, funcName, ...) 中参数是拼接字符串
    或跨文件变量，AST + 局部符号表都无法解析。

    Args:
        lua_content: hotfix lua 文件内容
        file_name: 文件名（仅用于日志）
        ext_logger: 可选外部 logger（如 app.logger）

    Returns: list of str，完整函数名列表（含 AI 补充结果）
    """
    log = ext_logger or logger
    try:
        from Implement.hotfixImpl import luaParserImp
        result = luaParserImp.extract_func_names(lua_content)
    except Exception as e:
        log.warning(f"hotfixFuncExtractor: AST extract failed for {file_name}: {e}")
        return _regex_extract(lua_content)

    func_names = result['func_names']
    unresolved = result.get('unresolved_calls', [])

    if not unresolved:
        return func_names

    # 构造 AI prompt
    unresolved_snippet = '\n'.join(unresolved)
    prompt = (
        f"以下是一段 Lua hotfix 文件（{file_name}）的代码：\n"
        f"```lua\n{lua_content}\n```\n\n"
        f"其中以下调用无法静态分析出参数值：\n"
        f"```lua\n{unresolved_snippet}\n```\n\n"
        "请分析整段代码（包括局部变量赋值、字符串拼接等），推断每个 HotfixComponentFunction 调用中 "
        "componentName 和 funcName 的实际字符串值。\n"
        "严格按如下 JSON 格式输出，不要有其他内容：\n"
        '{"results": [{"comp": "ComponentName", "func": "FuncName"}]}'
    )

    try:
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        req_data = json.dumps({'prompt': prompt, 'model': 'auto'}, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            _FLICKCLI_PROXY_URL,
            data=req_data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            ai_result = json.loads(resp.read().decode('utf-8'))

        if ai_result.get('code') == 0:
            review_text = ai_result.get('review', '')
            json_match = re.search(r'\{.*"results"\s*:.*\}', review_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                for item in parsed.get('results', []):
                    comp = item.get('comp', '').strip()
                    func = item.get('func', '').strip()
                    if comp and func:
                        fn = f"{comp}.{func}"
                        if fn not in func_names:
                            func_names.append(fn)
                            log.info(f"hotfixFuncExtractor: AI resolved {fn} in {file_name}")
    except Exception as e:
        log.warning(f"hotfixFuncExtractor: AI fallback failed for {file_name}: {e}")

    return func_names


# ── 主入口 ────────────────────────────────────────────────────────────────

def extract_func_names(lua_content, file_name='unknown', ext_logger=None):
    """
    从 lua 内容提取修改的函数名列表。

    优先级：AST → AI fallback（有 unresolved 时）→ 正则 fallback（AST 整体崩溃时）

    Args:
        lua_content: hotfix lua 文件文本
        file_name: 文件名，仅用于日志
        ext_logger: 可选外部 logger

    Returns:
        list of str，格式 "ClassName.MethodName"
    """
    log = ext_logger or logger
    try:
        from Implement.hotfixImpl import luaParserImp
        result = luaParserImp.extract_func_names(lua_content)
        if result.get('parse_error'):
            log.warning(f"hotfixFuncExtractor: AST parse error in {file_name}, used regex fallback: {result['parse_error']}")
        if result.get('unresolved_calls'):
            log.debug(f"hotfixFuncExtractor: {len(result['unresolved_calls'])} unresolved calls in {file_name}, using AI fallback")
            return extract_func_names_with_ai_fallback(lua_content, file_name=file_name, ext_logger=log)
        return result['func_names']
    except Exception as e:
        log.warning(f"hotfixFuncExtractor: extract_func_names failed for {file_name}, fallback to regex: {e}")
        return _regex_extract(lua_content)
