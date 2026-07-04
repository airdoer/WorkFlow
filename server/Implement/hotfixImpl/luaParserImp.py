# 如果是windows，那么需要在import luaparser之前，先设置环境变量
import os
import sys
libPath = os.path.join(os.path.dirname(__file__), "../../lib/")
if libPath not in sys.path:
    sys.path.append(libPath)
from luaparser import ast
from luaparser.astnodes import *
from luaparser.utils.visitor import *


# HotfixComponentFunction 之类的注册函数名（项目约定）
_HOTFIX_CALL_FUNCS = {'HotfixComponentFunction'}


def _get_string_value(node):
    """
    尝试从 AST 节点提取字符串字面量值。
    支持 String 节点，不支持则返回 None。
    """
    if isinstance(node, String):
        return node.s
    return None


class MyLuaVisitor(ast.WalkVisitor):
    def __init__(self, source_code=None):
        super().__init__()
        self.source_code = source_code

        self.my_local_assigns = {}
        self.my_local_functions = {}
        self.my_functions = {}
        self.my_assigns = {}

        # Layer 2：局部变量字面量符号表 {var_name: str_value}
        # 只记录 local x = "literal" 形式，多次赋值则标记为 None（不可信）
        self._local_str_consts = {}

        # Layer 1：HotfixComponentFunction 调用提取的函数名
        # 每项格式: {'comp': str, 'func': str, 'confidence': 'literal'|'resolved'|'unresolved'}
        self.my_hotfix_calls = []

        # 无法静态解析的调用片段（供 AI fallback 使用）
        self.unresolved_calls = []

    def get_node_source(self, node):
        """Get the original source code for a node."""
        if self.source_code and node.start_char is not None and node.stop_char is not None:
            return self.source_code[node.start_char : node.stop_char + 1]
        # Fallback to reconstructing code if original source is not available
        return ast.to_lua_source(node)

    def _visit_list(self, nodes):
        """安全遍历节点列表，跳过非 AST 节点"""
        if isinstance(nodes, list):
            for n in nodes:
                if n is not None and not isinstance(n, (str, int, float, bool)):
                    try:
                        self.visit(n)
                    except Exception:
                        pass

    def _resolve_str(self, node):
        """
        尝试把一个 AST 参数节点解析为字符串值。
        支持：直接 String 字面量 / Name（查局部变量符号表）
        返回 (value, confidence): confidence 为 'literal' | 'resolved' | None
        """
        if isinstance(node, String):
            return node.s, 'literal'
        if isinstance(node, Name):
            val = self._local_str_consts.get(node.id)
            if val is not None:
                return val, 'resolved'
        return None, None

    @visitor(LocalAssign)
    def visit(self, node):
        self._nodes.append(node)
        self._visit_list(node.targets)
        name = "__".join([x.my_name for x in node.targets])
        self.my_local_assigns[name] = self.get_node_source(node)

        # Layer 2：收集 local x = "literal" 到符号表
        targets = node.targets
        values = node.values if node.values else []
        for t, v in zip(targets, values):
            var_name = getattr(t, 'id', None)
            if var_name is None:
                continue
            if isinstance(v, String):
                # 如果已存在且不同，标为不可信
                if var_name in self._local_str_consts and self._local_str_consts[var_name] != v.s:
                    self._local_str_consts[var_name] = None
                else:
                    self._local_str_consts[var_name] = v.s
            else:
                # 非字面量赋值，标为不可信
                self._local_str_consts[var_name] = None

    @visitor(LocalFunction)
    def visit(self, node):
        self._nodes.append(node)
        self.visit(node.name)
        self._visit_list(node.args)
        self._visit_list(node.body.body if hasattr(node.body, 'body') else [])

    @visitor(Name)
    def visit(self, node):
        self._nodes.append(node)
        node.my_name_list = [node.id]
        node.my_name = node.id

    @visitor(Index)
    def visit(self, node):
        self._nodes.append(node)
        self.visit(node.value)
        self.visit(node.idx)
        node.my_name_list = [node.value.my_name]
        node.my_name_list.extend(node.idx.my_name_list)
        node.my_name = "__".join(node.my_name_list)

    @visitor(Assign)
    def visit(self, node):
        self._nodes.append(node)
        self._visit_list(node.targets)
        name = "__".join([x.my_name for x in node.targets])
        self.my_assigns[name] = self.get_node_source(node)
        # self.visit(node.values)

    @visitor(Forin)
    def visit(self, node):
        # Forin先忽略
        pass

    @visitor(Chunk)
    def visit(self, node):
        self._nodes.append(node)
        for stmt in (node.body.body if hasattr(node.body, 'body') else []):
            self.visit(stmt)

    @visitor(Block)
    def visit(self, node):
        self._nodes.append(node)
        for stmt in (node.body if isinstance(node.body, list) else []):
            self.visit(stmt)

    @visitor(Method)
    def visit(self, node):
        raise("Method node is not supported")
        self._nodes.append(node)
        self.visit(node.source)
        self.visit(node.name)
        self.visit(node.args)
        self.visit(node.body)

    @visitor(Function)
    def visit(self, node):
        self._nodes.append(node)
        # function A.B(...) 或 function A:B(...) 或 function Foo(...)
        func_name_node = node.name
        if isinstance(func_name_node, Name):
            # 普通 function Foo(...)
            name_key = func_name_node.id
        elif isinstance(func_name_node, Index):
            # function A.B(...) 会被 luaparser 表示为 Index(Name("A"), Name("B"))
            self.visit(func_name_node)
            name_key = func_name_node.my_name.replace("__", ".")
        else:
            name_key = str(func_name_node)
        self.my_functions[name_key] = self.get_node_source(node)

    @visitor(Call)
    def visit(self, node):
        """Layer 1：识别 HotfixComponentFunction("Comp", "Func", ...) 调用"""
        self._nodes.append(node)
        func_node = node.func
        func_id = None
        if isinstance(func_node, Name):
            func_id = func_node.id
        elif isinstance(func_node, Index):
            pass  # 暂不处理 table.func(...) 形式

        if func_id in _HOTFIX_CALL_FUNCS:
            args = node.args if node.args else []
            if len(args) >= 2:
                comp_val, comp_conf = self._resolve_str(args[0])
                func_val, func_conf = self._resolve_str(args[1])

                if comp_val and func_val:
                    confidence = 'literal' if (comp_conf == 'literal' and func_conf == 'literal') else 'resolved'
                    self.my_hotfix_calls.append({
                        'comp': comp_val,
                        'func': func_val,
                        'func_name': f"{comp_val}.{func_val}",
                        'confidence': confidence,
                    })
                else:
                    # 无法静态解析，记录调用源码供 AI fallback
                    self.unresolved_calls.append(self.get_node_source(node))


def analyze_lua_code(code_str) -> MyLuaVisitor:
    tree = ast.parse(code_str)
    analyzer = MyLuaVisitor(code_str)
    analyzer.visit(tree)
    return analyzer


def _walk_all_nodes(tree):
    """
    自定义 AST 全量遍历，不依赖 luaparser 的 visitor 机制，
    直接递归所有节点属性，避免 VisitorException。
    """
    from luaparser.astnodes import Node
    visited = set()
    stack = [tree]
    while stack:
        node = stack.pop()
        if node is None or id(node) in visited:
            continue
        if not isinstance(node, Node):
            continue
        visited.add(id(node))
        yield node
        # 遍历所有属性，把子节点加入栈
        for attr in vars(node).values():
            if isinstance(attr, Node):
                stack.append(attr)
            elif isinstance(attr, list):
                for item in attr:
                    if isinstance(item, Node):
                        stack.append(item)


def extract_func_names(lua_content):
    """
    Layer 1 + Layer 2：用 AST 提取 hotfix 文件中修改的函数名列表。

    不依赖 MyLuaVisitor，直接用 ast.walk() 遍历，避免 VisitorException。

    支持写法：
    - A.B = function(...)          -> Assign 节点
    - function A.B(...)            -> Function 节点
    - function A:B(...)            -> Function 节点
    - HotfixComponentFunction("A", "B", ...)  -> Call 节点（字面量）
    - HotfixComponentFunction(compVar, funcVar, ...)  -> Call 节点 + 局部变量符号表（Layer 2）

    Returns:
        dict with keys:
          - 'func_names': list of str
          - 'confidence': dict mapping func_name -> confidence tag
          - 'unresolved_calls': list of str，无法静态解析的调用源码片段
          - 'parse_error': str or None
    """
    try:
        tree = ast.parse(lua_content)
    except Exception as e:
        return _extract_func_names_regex_fallback(lua_content, parse_error=str(e))

    func_names = []
    confidence = {}
    unresolved_calls = []

    # Layer 2：先收集所有顶层 local x = "literal" 到符号表
    local_str_consts = {}
    for node in _walk_all_nodes(tree):
        if isinstance(node, LocalAssign):
            targets = node.targets or []
            values = node.values or []
            for t, v in zip(targets, values):
                var_name = getattr(t, 'id', None)
                if var_name is None:
                    continue
                if isinstance(v, String):
                    s = v.s
                    if isinstance(s, bytes):
                        s = s.decode('utf-8', errors='replace')
                    if var_name in local_str_consts and local_str_consts[var_name] != s:
                        local_str_consts[var_name] = None  # 多次赋值，不可信
                    else:
                        local_str_consts[var_name] = s
                else:
                    local_str_consts[var_name] = None

    def resolve_str(node):
        if isinstance(node, String):
            s = node.s
            if isinstance(s, bytes):
                s = s.decode('utf-8', errors='replace')
            return s, 'literal'
        if isinstance(node, Name):
            val = local_str_consts.get(node.id)
            if val is not None:
                return val, 'resolved'
        return None, None

    def node_to_name(node):
        """把 Name 或 Index 节点转成 A.B 格式字符串"""
        if isinstance(node, Name):
            return node.id
        if isinstance(node, Index):
            parent = node_to_name(node.value)
            idx = node_to_name(node.idx)
            if parent and idx:
                return f"{parent}.{idx}"
        return None

    def add_func(name, conf):
        if name and name not in func_names:
            func_names.append(name)
            confidence[name] = conf

    for node in _walk_all_nodes(tree):
        # A.B = function(...)
        if isinstance(node, Assign):
            targets = node.targets or []
            values = node.values or []
            for t, v in zip(targets, values):
                if isinstance(v, (AnonymousFunction,)) or (
                    hasattr(v, '__class__') and 'Function' in type(v).__name__
                ):
                    name = node_to_name(t)
                    if name and '.' in name:
                        add_func(name, 'assign')
            # 也检查源码中含 function 关键字的赋值（兜底）
            for t in targets:
                name = node_to_name(t)
                if name and '.' in name:
                    try:
                        src = lua_content[node.start_char:node.stop_char + 1] if node.start_char is not None else ''
                        if '= function' in src or '=function' in src:
                            add_func(name, 'assign')
                    except Exception:
                        pass

        # function A.B(...) / function A:B(...)
        elif isinstance(node, Function):
            name = node_to_name(node.name)
            if name:
                add_func(name, 'funcdef')

        # function A:B(...) -> Method 节点（luaparser 区分 Function 和 Method）
        elif isinstance(node, Method):
            source_name = node_to_name(node.source)
            method_name = node_to_name(node.name)
            if source_name and method_name:
                add_func(f"{source_name}.{method_name}", 'methoddef')

        # HotfixComponentFunction("A", "B", ...)
        elif isinstance(node, Call):
            func_node = node.func
            func_id = getattr(func_node, 'id', None)
            if func_id in _HOTFIX_CALL_FUNCS:
                args = node.args or []
                if len(args) >= 2:
                    comp_val, comp_conf = resolve_str(args[0])
                    func_val, func_conf = resolve_str(args[1])
                    if comp_val and func_val:
                        conf = 'literal' if (comp_conf == 'literal' and func_conf == 'literal') else 'resolved'
                        add_func(f"{comp_val}.{func_val}", conf)
                    else:
                        try:
                            src = lua_content[node.start_char:node.stop_char + 1] if node.start_char is not None else str(node)
                        except Exception:
                            src = str(node)
                        unresolved_calls.append(src)

    return {
        'func_names': func_names,
        'confidence': confidence,
        'unresolved_calls': unresolved_calls,
        'parse_error': None,
    }


def _extract_func_names_regex_fallback(lua_content, parse_error=None):
    """
    AST 解析失败时的正则降级方案（多模式）。
    """
    import re
    patterns = [
        re.compile(r'^([\w.]+)\.(\w+)\s*=\s*function\s*\('),       # A.B = function
        re.compile(r'^function\s+([\w.]+)\.(\w+)\s*\('),           # function A.B(...)
        re.compile(r'^function\s+([\w.]+):(\w+)\s*\('),            # function A:B(...)
    ]
    # HotfixComponentFunction 字面量参数
    hotfix_call_pattern = re.compile(
        r'HotfixComponentFunction\s*\(\s*["\'](\w+)["\']\s*,\s*["\'](\w+)["\']\s*,'
    )

    func_names = []
    confidence = {}

    for line in lua_content.strip().split('\n'):
        stripped = line.strip()
        if stripped.startswith('--') or stripped.startswith('print'):
            continue
        for pat in patterns:
            m = pat.match(stripped)
            if m:
                fn = f"{m.group(1)}.{m.group(2)}"
                if fn not in func_names:
                    func_names.append(fn)
                    confidence[fn] = 'regex'
                break
        m = hotfix_call_pattern.search(stripped)
        if m:
            fn = f"{m.group(1)}.{m.group(2)}"
            if fn not in func_names:
                func_names.append(fn)
                confidence[fn] = 'regex'

    return {
        'func_names': func_names,
        'confidence': confidence,
        'unresolved_calls': [],
        'parse_error': parse_error,
    }


def analyze_lua_file(filepath):
    with open(filepath, "r", encoding="utf8") as f:
        code = f.read()

    tree = ast.parse(code)
    print(f"Parsed {filepath} successfully.")
    
    print(ast.to_pretty_str(tree))

    analyzer = MyLuaVisitor(code)
    analyzer.visit(tree)
            
    # print(f"Found {analyzer.func_count} functions and {analyzer.assign_count} assignments.")
    

def _compare_code(code_visitor1: MyLuaVisitor, code_visitor2: MyLuaVisitor):
    """比较两个Lua代码的解析结果差异"""
    diffs = []
    for my_attr in ['my_local_assigns', 'my_local_functions', 'my_functions', 'my_assigns']:
        for name in getattr(code_visitor1, my_attr):
            if name not in getattr(code_visitor2, my_attr):
                diffs.append({
                    'diff_type': 'delete',
                    'code_type': my_attr,
                    'name': name,
                    'code': ""
                })
            else:
                if getattr(code_visitor2, my_attr)[name] != getattr(code_visitor1, my_attr)[name]:
                    diffs.append({
                        'diff_type': 'modify',
                        'code_type': my_attr,
                        'name': name,
                        'code': getattr(code_visitor2, my_attr)[name]
                    })
        for name in getattr(code_visitor2, my_attr):
            if name not in getattr(code_visitor1, my_attr):
                diffs.append({
                    'diff_type': 'add',
                    'code_type': my_attr,
                    'name': name,
                    'code': getattr(code_visitor2, my_attr)[name]
                })
    return diffs


def analyze_lua_example():
    code = """
    function MyClass:method() end
    MyClass.method = function() end
    MyClass.field = 10
    """
    tree = ast.parse(code)
    print("--- AST Structure ---")
    print(ast.to_pretty_str(tree))
    
    print("\n--- Analysis ---")
    analyzer = MyLuaVisitor(code)
    analyzer.visit(tree)

def czxTest():
    # luaFilePath = "/app/p4WorkSpace/C7/Development/Mainline/Server/script_lua/Logic/Entities/AvatarActor.lua#198"
    # 198到199是修改了AvatarActor.onDayRefresh函数
    # luaFilePath = "/app/p4WorkSpace/C7/Development/Mainline/Server/script_lua/Logic/Entities/AvatarActor.lua#199"
    # 199到200是新增了AvatarActor.onServiceRemoved函数
    # luaFilePath = "/app/p4WorkSpace/C7/Development/Mainline/Server/script_lua/Logic/Entities/AvatarActor.lua#200"
    # luaFilePath = r"C:\Users\ADMINI~1\AppData\Local\Temp\p4v\GM0NGBW4_172.20.6.45_1666_utf8\C7\Development\Mainline\Server\script_lua\Logic\Entities\AvatarActor#198.lua"
    # luaFilePath = r"E:\Code\github\game-watchman\server\p4WorkSpace\C7\Development\Mainline\Server\script_lua\Logic\Entities\AvatarActor111.lua"
    luaFilePath = r"E:\Code\github\game-watchman\server\p4WorkSpace\C7\Development\Mainline\Server\script_lua\Data\Formula\CommonFormulaFuncData.lua"
    analyze_lua_file(luaFilePath)


# ------------------------------------------
#  CLI
# ------------------------------------------

# 目标，把code1和code2中的diff找到，并且分析出差异的模块/类/函数/方法/字段/赋值
# 把code2中的require的部分也找到
# 最终让AI来生成新的代码

if __name__ == "__main__":
    # analyze_lua_example()
    czxTest()
