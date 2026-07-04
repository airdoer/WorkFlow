from typing import Any

from lupa import LuaRuntime
import re
import logging
import os
from utility import p4Utils
from Implement.hotfixImpl.combat_data_hotfix_config import CombatDataHotfixCfgModule
from Implement.aiImpl import aiImp
from Implement.hotfixImpl import luaParserImp
import config
from data.C7.FormulaConfig import TableName2RuntimeName


HOTFIX_ENV_LUA = ""
_hotfix_env_path = os.path.join(os.path.dirname(__file__), "hotfix_env.lua")
try:
    with open(_hotfix_env_path, "r", encoding="utf-8") as f:
        HOTFIX_ENV_LUA = f.read()
except Exception as e:
    logging.error("Failed to read hotfix_env.lua: %s", e)

LUA_HOTFIX_PATH_BLACKLIST_PATTERNS = [
    re.compile(r'/Client/Content/Script/Data/Config/BattleSystem/AbilitySystem/MoveByAnim/[^#]*\.lua', re.IGNORECASE),
    re.compile(r'/Client/Content/Script/Data/Excel/SkillDataEditor[^#]*\.lua', re.IGNORECASE),
    re.compile(r'/Client/Content/Script/Data/Excel/TableData\.lua', re.IGNORECASE),
    re.compile(r'/Client/Content/Script/Data/Config/MapDataNew/.*\.lua', re.IGNORECASE),
    re.compile(r'/Client/Content/Script/Data/Excel/Annotation/.*\.lua', re.IGNORECASE),
    re.compile(r'/Client/Content/Script/Data/Config/Dialogue/.*\.lua', re.IGNORECASE),
    re.compile(r'/Server/script_lua/Data/Excel/Annotation/.*\.lua', re.IGNORECASE),
    re.compile(r'/Server/script_lua/Data/Excel/TableData\.lua', re.IGNORECASE),
    re.compile(r'/Server/script_lua/Data/SkillData/Skill/.*\.lua', re.IGNORECASE)
]

def _is_blacklisted_raw_file_path(raw_file_path: str) -> bool:
    return any(p.search(raw_file_path or "") for p in LUA_HOTFIX_PATH_BLACKLIST_PATTERNS)

class LoggerWithInfo:
    def __init__(self, entity):
        self.entity = entity  # 不用考虑循环引用

    def info(self, *message):
        logging.info(f"{self.entity.logHeader} {message[0]}", *message[1:])
    
    def error(self, *message):
        logging.error(f"{self.entity.logHeader} {message[0]}", *message[1:])

# region LuaHelperWrapper
class LuaLangStringWrapper:
    def __init__(self, str_idx):
        self.str_idx = str_idx

    def __repr__(self):
        return f"<LuaLangString {self.str_idx}>"

class LuaLangStringSplitWrapper:
    def __init__(self, str_idx, tag):
        self.str_idx = str_idx
        self.tag = tag

    def __repr__(self):
        return f"<LuaLangStringSplit {self.str_idx}>{self.tag}"

class LuaNilWrapper: 
    def __repr__(self):
        return "nil"
    
class LuaEmptyTableWrapper: 
    def __repr__(self):
        return "{}"

class LuaFVectorWrapper:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def __eq__(self, val):
        return self.x == val.x and self.y == val.y and self.z == val.z

    def __repr__(self):
        return f"FVector({self.x}, {self.y}, {self.z})"
    
class LuaFVector2DWrapper:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, val):
        return self.x == val.x and self.y == val.y

    def __repr__(self):
        return f"FVector2D({self.x}, {self.y})"

class LuaFRotatorWrapper:
    def __init__(self, pitch, yaw, roll):
        self.pitch = pitch
        self.yaw = yaw
        self.roll = roll

    def __eq__(self, val):
        return self.pitch == val.pitch and self.yaw == val.yaw and self.roll == val.roll

    def __repr__(self):
        return f"FRotator({self.pitch}, {self.yaw}, {self.roll})"
    
class LuaFQuatWrapper:
    def __init__(self, x, y, z, w):
        self.x = x
        self.y = y
        self.z = z
        self.w = w

    def __eq__(self, val):
        return self.x == val.x and self.y == val.y and self.z == val.z and self.w == val.w

    def __repr__(self):
        return f"FQuat({self.x}, {self.y}, {self.z}, {self.w})"

class LuaFTransformWrapper:
    def __init__(self, type, *args):
        self.type = type
        self.args = args

    def __eq__(self, val):
        return self.type == val.type and self.args == val.args

    def __repr__(self):
        # 注意：self.args 是 *args 收集到的 tuple，直接 f"{self.args}" 会带一层 tuple 的外括号，
        # 导致生成类似 FTransform((...)) 的格式；这里改为逐个拼接，输出 FTransform(a, b, c)。
        args_str = ", ".join(str(a) for a in self.args)
        return f"FTransform({args_str})"
    
class LuaFColorWrapper:
    def __init__(self, x, y, z, w):
        self.x = x
        self.y = y
        self.z = z
        self.w = w

    def __eq__(self, val):
        return self.x == val.x and self.y == val.y and self.z == val.z and self.w == val.w

    def __repr__(self):
        return f"FColor({self.x}, {self.y}, {self.z}, {self.w})"
# region LuaHelperWrapper end

class LuaEnv:
    def __init__(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.logHeader = "LuaEnv"
        self.logger = LoggerWithInfo(self)

    def add_lua_search_path(self, path):
        # 转成 Lua 风格路径（防止 Windows 反斜杠问题）
        lua_path = path.replace("\\", "/")
        # 在 package.path 里追加路径模式
        self.lua.execute(f'package.path = package.path .. ";{lua_path}/?.lua"')

    def lua_execute(self, exec_str):
        self.lua.execute(exec_str)

    def check_lua_content(self, hotfix_content):
        try:
            self.lua.compile(hotfix_content)
            return True, None
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Lua syntax validation failed: {error_msg}")
            return False, error_msg

    def prepare_env(self):
        self.lua.globals().LuaLangString = LuaLangStringWrapper
        self.lua.globals().LuaLangStrSplit = LuaLangStringSplitWrapper
        self.lua.globals().LuaFVector = LuaFVectorWrapper
        self.lua.globals().LuaFRotator = LuaFRotatorWrapper
        self.lua.globals().LuaFVector2D = LuaFVector2DWrapper
        self.lua.globals().LuaFQuat = LuaFQuatWrapper
        self.lua.globals().LuaFTransform = LuaFTransformWrapper
        self.lua.globals().LuaFColor = LuaFColorWrapper
        if HOTFIX_ENV_LUA:
            self.lua_execute(HOTFIX_ENV_LUA)

    def lua_table_to_dict(self, lua_table):
        if self.lua.globals().type(lua_table) == 'table':
            # 检查是否为数组
            keys = list(lua_table.keys())
            if keys and all(isinstance(key, int) for key in keys) and keys == list(range(1, len(keys)+1)):
                # 是数组，转换为Python列表
                return [self.lua_table_to_dict(lua_table[i]) for i in range(1, len(keys)+1)]
            else:
                # 是字典，转换为Python字典
                return {key: self.lua_table_to_dict(value) for key, value in lua_table.items()}
        else:
            return lua_table

    def load_lua_file(self, file_name):
        # 这里的file_name是绝对路径，因为dofile认绝对路径
        try:
            lua_data = self.lua.execute(f'return dofile("{file_name}")')
            # 转换 Lua 表为 Python 字典
            python_dict = self.lua_table_to_dict(lua_data)
            return python_dict 
        except Exception as e:
            self.logger.error("load_lua_file failed %s \nexception: %s", file_name, e)
            return {}
    
    def load_lua_content(self, content, file_name, target_var_name = None):
        # 使用更安全的方法来处理Lua内容
        # 先尝试直接执行内容
        try:
            lua_data = self.lua.execute(content)
            if target_var_name:
                lua_data = self.lua.globals()[target_var_name]
            # 转换 Lua 表为 Python 字典
            python_dict = self.lua_table_to_dict(lua_data)
            return python_dict
        except Exception as e:
            # 如果直接执行失败，尝试使用load函数
            # 使用Lua的长字符串语法来避免转义问题
            # 找到一个不在内容中出现的分隔符
            delimiter = "]]"
            counter = 0
            while delimiter in content:
                counter += 1
                delimiter = "]" + "=" * counter + "]"
            
            long_string_start = "[" + "=" * counter + "["
            long_string_end = delimiter
            
            lua_code = f"return (load({long_string_start}{content}{long_string_end}, {repr(file_name)}))()"
            lua_data = self.lua.execute(lua_code)
            # 转换 Lua 表为 Python 字典
            python_dict = self.lua_table_to_dict(lua_data)
            return python_dict


# def test_luaenv():
#     return LuaEnv()

# def test_func():
#     lua_env = LuaEnv()
#     lua_env.prepare_env()
#     return lua_env.require_lua_data("/app/p4WorkSpace/Mainline/Server/script_lua/tmp/Data/Excel/ClimateConstData.lua")


LONG_LIST_THRESHOLD = 4

def _get_element_type_key(item):
    """返回列表元素的类型标识，用于判断是否为同类型元素"""
    if type(item) in (int, float):
        return 'number'  # int 和 float 统一视为数值类型
    elif type(item) in (bool, str):
        return type(item)
    elif isinstance(item, (LuaLangStringWrapper, LuaLangStringSplitWrapper,
                            LuaFVectorWrapper, LuaFVector2DWrapper, LuaFRotatorWrapper,
                            LuaFQuatWrapper, LuaFTransformWrapper, LuaFColorWrapper)):
        return type(item)
    elif isinstance(item, list):
        if not item:
            return ('list', 0)
        sub_types = tuple(_get_element_type_key(x) for x in item)
        if any(t is None for t in sub_types):
            return None
        return ('list', sub_types)
    else:
        return None  # dict/list/unknown，不视为固定类型

def _is_fixed_type_list(lst):
    """判断列表是否为长度>LONG_LIST_THRESHOLD且元素均为同一固定类型的list"""
    if len(lst) <= LONG_LIST_THRESHOLD:
        return False
    if not lst:
        return False
    first_type = _get_element_type_key(lst[0])
    if first_type is None:
        return False
    return all(_get_element_type_key(item) == first_type for item in lst)


def _is_all_elements_changed(old_list, new_list):
    """判断新旧list每个对应元素都发生了变化（旧list为空时视为全部新增）"""
    if len(old_list) == 0:
        return len(new_list) > 0
    if len(old_list) != len(new_list):
        return False
    return all(old_list[i] != new_list[i] for i in range(len(old_list)))


def _get_sublist_element_type_key(item):
    """返回list元素的类型标识（含list子类型），用于_is_uniform_sublist_list"""
    if type(item) in (int, float):
        return 'number'
    elif type(item) in (bool, str):
        return type(item)
    elif isinstance(item, list):
        if not item:
            return ('list', 0)
        sub_types = tuple(_get_sublist_element_type_key(x) for x in item)
        if any(t is None for t in sub_types):
            return None
        return ('list', sub_types)
    else:
        return None

def _is_uniform_sublist_list(lst):
    """判断list是否为长度>LONG_LIST_THRESHOLD且每个元素均为同构短list（如 {int,int}）"""
    if len(lst) <= LONG_LIST_THRESHOLD:
        return False
    if not lst or not isinstance(lst[0], list):
        return False
    first_type = _get_sublist_element_type_key(lst[0])
    if first_type is None:
        return False
    return all(_get_sublist_element_type_key(item) == first_type for item in lst)


def _make_long_list_tag_paths(base_path, old_list, new_list):
    """为长list生成用于tag展示的逐元素路径列表"""
    tag_paths = []
    max_len = max(len(old_list), len(new_list))
    for i in range(max_len):
        lua_idx = i + 1
        old_item = old_list[i] if i < len(old_list) else None
        new_item = new_list[i] if i < len(new_list) else None
        if old_item != new_item:
            tag_paths.append(base_path + [lua_idx])
    return tag_paths


def _compare_dict(old_dict, new_dict, path):
    """比较两个字典并返回差异信息"""
    diffs = []
    
    # 检查删除的键
    for key in old_dict:
        if key not in new_dict:
            diffs.append({
                'diff_type': 'delete',
                'path': path + [key],
                'value': None
            })
        else:
            # 递归比较嵌套字典
            old_val = old_dict[key]
            new_val = new_dict[key]
            
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                nested_diffs = _compare_dict(old_val, new_val, path + [key])
                diffs.extend(nested_diffs)
            elif isinstance(old_val, list) and isinstance(new_val, list):
                # 对于长度>LONG_LIST_THRESHOLD且元素为同一固定类型的list，且全部index都被重新赋值，直接以整个list作为diff value
                if _is_fixed_type_list(new_val) and old_val != new_val and _is_all_elements_changed(old_val, new_val):
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [key],
                        'value': new_val,
                        'tag_paths': _make_long_list_tag_paths(path + [key], old_val, new_val)
                    })
                else:
                    nested_diffs = _compare_list(old_val, new_val, path + [key])
                    diffs.extend(nested_diffs)
            elif isinstance(old_val, dict) and len(old_val) == 0 and isinstance(new_val, list):
                if _is_fixed_type_list(new_val) and _is_all_elements_changed([], new_val):
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [key],
                        'value': new_val,
                        'tag_paths': _make_long_list_tag_paths(path + [key], [], new_val)
                    })
                else:
                    nested_diffs = _compare_list([], new_val, path + [key])
                    diffs.extend(nested_diffs)
            elif isinstance(old_val, list) and isinstance(new_val, dict) and len(new_val) == 0:
                nested_diffs = _compare_list(old_val, [], path + [key])
                diffs.extend(nested_diffs)
            elif isinstance(old_val, list) and isinstance(new_val, dict) and len(new_val) > 0:
                # Lua table 特性：list 转换为 dict（有非连续索引或从非1开始）
                # 将 list 转换为 dict 进行比较（list索引从0开始，转为lua索引从1开始）
                old_as_dict = {i + 1: item for i, item in enumerate(old_val)}
                nested_diffs = _compare_dict(old_as_dict, new_val, path + [key])
                diffs.extend(nested_diffs)
            elif isinstance(old_val, dict) and len(old_val) > 0 and isinstance(new_val, list):
                # Lua table 特性：dict 转换为 list（变成连续索引且从1开始）
                # 将 list 转换为 dict 进行比较
                new_as_dict = {i + 1: item for i, item in enumerate(new_val)}
                nested_diffs = _compare_dict(old_val, new_as_dict, path + [key])
                diffs.extend(nested_diffs)
            elif isinstance(old_val, LuaLangStringWrapper) and isinstance(new_val, LuaLangStringWrapper):
                if old_val.str_idx != new_val.str_idx:
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [key],
                        'value': new_val
                    })
            elif isinstance(old_val, LuaLangStringSplitWrapper) and isinstance(new_val, LuaLangStringSplitWrapper):
                if old_val.str_idx != new_val.str_idx or old_val.tag != new_val.tag:
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [key],
                        'value': new_val
                    })
            elif isinstance(old_val, LuaLangStringWrapper) and isinstance(new_val, LuaLangStringSplitWrapper):
                diffs.append({
                    'diff_type': 'modify',
                    'path': path + [key],
                    'value': new_val
                })
            elif isinstance(old_val, LuaLangStringSplitWrapper) and isinstance(new_val, LuaLangStringWrapper):
                diffs.append({
                    'diff_type': 'modify',
                    'path': path + [key],
                    'value': new_val
                })
            elif isinstance(old_val, LuaFVectorWrapper) and isinstance(new_val, LuaFVectorWrapper):
                if old_val != new_val:
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [key],
                        'value': new_val
                    })
            elif isinstance(old_val, LuaFVector2DWrapper) and isinstance(new_val, LuaFVector2DWrapper):
                if old_val != new_val:
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [key],
                        'value': new_val
                    })
            elif isinstance(old_val, LuaFRotatorWrapper) and isinstance(new_val, LuaFRotatorWrapper):
                if old_val != new_val:
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [key],
                        'value': new_val
                    })
            elif isinstance(old_val, LuaFQuatWrapper) and isinstance(new_val, LuaFQuatWrapper):
                if old_val != new_val:
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [key],
                        'value': new_val
                    })
            elif isinstance(old_val, LuaFTransformWrapper) and isinstance(new_val, LuaFTransformWrapper):
                if old_val != new_val:
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [key],
                        'value': new_val
                    })
            elif isinstance(old_val, LuaFColorWrapper) and isinstance(new_val, LuaFTransformWrapper):
                if old_val != new_val:
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [key],
                        'value': new_val
                    })
            elif old_val != new_val:
                diffs.append({
                    'diff_type': 'modify',
                    'path': path + [key],
                    'value': new_val
                })
    
    # 检查新增的键
    for key in new_dict:
        if key not in old_dict:
            diffs.append({
                'diff_type': 'add',
                'path': path + [key],
                'value': new_dict[key]
            })
    
    return diffs


def _compare_list(old_list, new_list, path):
    """比较两个列表并返回差异信息"""
    diffs = []
    
    # 检查删除的元素
    for i, old_item in enumerate(old_list):
        lua_idx = i + 1
        if lua_idx > len(new_list):
            diffs.append({
                'diff_type': 'delete',
                'path': path + [lua_idx], # lua的idx从1开始
                'value': None
            })
        else:
            new_item = new_list[i]
            
            if isinstance(old_item, dict) and isinstance(new_item, dict):
                nested_diffs = _compare_dict(old_item, new_item, path + [lua_idx])
                diffs.extend(nested_diffs)
            elif isinstance(old_item, list) and isinstance(new_item, list):
                # 对于长度>LONG_LIST_THRESHOLD且元素为同一固定类型的list，且全部index都被重新赋值，直接以整个list作为diff value
                if _is_fixed_type_list(new_item) and old_item != new_item and _is_all_elements_changed(old_item, new_item):
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [lua_idx],
                        'value': new_item
                    })
                else:
                    nested_diffs = _compare_list(old_item, new_item, path + [lua_idx])
                    diffs.extend(nested_diffs)
            elif isinstance(old_item, dict) and len(old_item) == 0 and isinstance(new_item, list):
                if _is_fixed_type_list(new_item) and _is_all_elements_changed([], new_item):
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [lua_idx],
                        'value': new_item
                    })
                else:
                    nested_diffs = _compare_list([], new_item, path + [lua_idx])
                    diffs.extend(nested_diffs)
            elif isinstance(old_item, list) and isinstance(new_item, dict) and len(new_item) == 0:
                nested_diffs = _compare_list(old_item, [], path + [lua_idx])
                diffs.extend(nested_diffs)
            elif isinstance(old_item, LuaLangStringWrapper) and isinstance(new_item, LuaLangStringWrapper):
                if old_item.str_idx != new_item.str_idx:
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [lua_idx],
                        'value': new_item
                    })
            elif isinstance(old_item, LuaLangStringSplitWrapper) and isinstance(new_item, LuaLangStringSplitWrapper):
                if old_item.str_idx != new_item.str_idx or old_item.tag != new_item.tag:
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [lua_idx],
                        'value': new_item
                    })
            elif isinstance(old_item, LuaLangStringWrapper) and isinstance(new_item, LuaLangStringSplitWrapper):
                diffs.append({
                    'diff_type': 'modify',
                    'path': path + [lua_idx],
                    'value': new_item
                })
            elif isinstance(old_item, LuaLangStringSplitWrapper) and isinstance(new_item, LuaLangStringWrapper):
                diffs.append({
                    'diff_type': 'modify',
                    'path': path + [lua_idx],
                    'value': new_item
                })
            elif isinstance(old_item, LuaFVectorWrapper) and isinstance(new_item, LuaFVectorWrapper):
                if old_item != new_item:
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [lua_idx],
                        'value': new_item
                    })
            elif isinstance(old_item, LuaFVector2DWrapper) and isinstance(new_item, LuaFVector2DWrapper):
                if old_item != new_item:
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [lua_idx],
                        'value': new_item
                    })
            elif isinstance(old_item, LuaFRotatorWrapper) and isinstance(new_item, LuaFRotatorWrapper):
                if old_item != new_item:
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [lua_idx],
                        'value': new_item
                    })
            elif isinstance(old_item, LuaFQuatWrapper) and isinstance(new_item, LuaFQuatWrapper):
                if old_item != new_item:
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [lua_idx],
                        'value': new_item
                    })
            elif isinstance(old_item, LuaFTransformWrapper) and isinstance(new_item, LuaFTransformWrapper):
                if old_item != new_item:
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [lua_idx],
                        'value': new_item
                    })
            elif isinstance(old_item, LuaFColorWrapper) and isinstance(new_item, LuaFColorWrapper):
                if old_item != new_item:
                    diffs.append({
                        'diff_type': 'modify',
                        'path': path + [lua_idx],
                        'value': new_item
                    })
            elif old_item != new_item:
                diffs.append({
                    'diff_type': 'modify',
                    'path': path + [lua_idx],
                    'value': new_item
                })
    
    # 检查新增的元素
    for i in range(len(old_list), len(new_list)):
        lua_idx = i + 1
        diffs.append({
            'diff_type': 'add',
            'path': path + [lua_idx],
            'value': new_list[i]
        })
    
    return diffs

def _generate_hotfix_data_path(path):
    pathStr = ""
    for _path_part in path:
        if isinstance(_path_part, int):
            pathStr += f"[{_path_part}]"
        elif isinstance(_path_part, str):
            # 检查是否为合法的 Lua 标识符：字母或下划线开头，仅包含字母数字下划线
            if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', _path_part):
                pathStr += f".{_path_part}"
            else:
                # 包含中文、数字开头、特殊字符等，使用中括号形式
                escaped_part = _path_part.replace("'", "\\'")
                pathStr += f"['{escaped_part}']"
        else:
            pathStr += f".{_path_part}"
    return pathStr

def _is_simple_type(value):
    if type(value) in [int, float, bool, str]:
        return true
    return false

def _format_lua_value(value, indent=0, use_newline=False, indent_step=4, complexity_threshold=2):
    """
    将Python值格式化为Lua字符串
    :param indent: 当前缩进空格数
    :param use_newline: 是否强制使用换行
    :param indent_step: 每级缩进空格数
    :param complexity_threshold: 列表或字典元素数超过该值时，换行显示
    """
    space = ' ' * indent
    if value is None:
        return 'nil'
    elif isinstance(value, str):
        # 处理转义字符
        value = value.replace('\\', '\\\\')
        value = value.replace('"', '\\"')
        value = value.replace('\n', '\\n')
        value = value.replace('\r', '\\r')
        value = value.replace('\t', '\\t')
        return f'"{value}"'
    elif isinstance(value, bool):
        return 'true' if value else 'false'
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, LuaNilWrapper):
        return "nil"
    elif isinstance(value, LuaEmptyTableWrapper):
        return "{}"
    elif isinstance(value, LuaLangStringWrapper):
        return f"Game.TableDataManager:GetLangStr('{value.str_idx}')"
    elif isinstance(value, LuaLangStringSplitWrapper):
        return f"LangStrSplit('{value.str_idx}', '{value.tag}')"
    elif isinstance(value, LuaFVectorWrapper):
        return f"FVector({value.x}, {value.y}, {value.z})"
    elif isinstance(value, LuaFRotatorWrapper):
        return f"FRotator({value.pitch}, {value.yaw}, {value.roll})"
    elif isinstance(value, LuaFVector2DWrapper):
        return f"FVector2D({value.x}, {value.y})"
    elif isinstance(value, LuaFQuatWrapper):
        return f"FQuat({value.x}, {value.y}, {value.z}, {value.w})"
    elif isinstance(value, LuaFTransformWrapper):
        inner_items = [_format_lua_value(i, indent, False, indent_step, complexity_threshold) for i in value.args]
        return f"FTransform({', '.join(inner_items)})"
    elif isinstance(value, LuaFColorWrapper):
        return f"FColor({value.x}, {value.y}, {value.z}, {value.w})"
    elif isinstance(value, list):
        # 长list且元素均为同构简单list（如 {int, int}），整体单行显示
        if _is_uniform_sublist_list(value):
            inner_items = [_format_lua_value(i, indent, False, indent_step, complexity_threshold) for i in value]
            return '{' + ', '.join(inner_items) + '}'
        # 纯基础数值类型的长list，强制单行显示
        if _is_fixed_type_list(value):
            inner_items = [_format_lua_value(i, indent, False, indent_step, complexity_threshold) for i in value]
            return '{' + ', '.join(inner_items) + '}'
        # 检查复杂度：长度、是否包含嵌套结构
        is_complex = (
            len(value) > complexity_threshold or
            any(isinstance(i, (list, dict)) for i in value)
        )
        if is_complex:
            inner_items = [
                ' ' * (indent + indent_step) + _format_lua_value(i, indent + indent_step, True, indent_step, complexity_threshold)
                for i in value
            ]
            return f'{{\n' + ',\n'.join(inner_items) + f'\n{space}}}'
        else:
            inner_items = [_format_lua_value(i, indent, False, indent_step, complexity_threshold) for i in value]
            return '{' + ', '.join(inner_items) + '}'
    elif isinstance(value, dict):
        is_complex = (
            len(value) >= complexity_threshold or
            any(isinstance(v, (list, dict)) for v in value.values())
        )
        if is_complex:
            inner_items = [
                ' ' * (indent + indent_step) + f"[{_format_lua_value(k)}] = {_format_lua_value(v, indent + indent_step, True, indent_step, complexity_threshold)}"
                for k, v in value.items()
            ]
            return f'{{\n' + ',\n'.join(inner_items) + f'\n{space}}}'
        else:
            inner_items = [f"[{_format_lua_value(k)}] = {_format_lua_value(v, indent, False, indent_step, complexity_threshold)}" for k, v in value.items()]
            return '{' + ', '.join(inner_items) + '}'
    else:
        return str(value)

def _get_hotfix_log(hotfixTYpe):
    if hotfixTYpe == 'server':
        return 'LOG_INFO_FMT'
    elif hotfixTYpe == 'client':
        return 'print'

def _merge_lua_loaded_data(merged, part):
    if merged is None:
        merged = {}
    if part is None:
        return merged
    if isinstance(merged, dict) and isinstance(part, dict):
        if 'data' in part and isinstance(part.get('data'), dict):
            merged_data = merged.get('data')
            if not isinstance(merged_data, dict):
                merged_data = {}
                merged['data'] = merged_data
            merged_data.update(part.get('data') or {})
            for k, v in part.items():
                if k == 'data':
                    continue
                if k not in merged:
                    merged[k] = v
            return merged
        merged.update(part)
        return merged
    if isinstance(merged, list) and isinstance(part, list):
        merged.extend(part)
        return merged
    if merged in ({}, [], None):
        return part
    return merged

def generate_hotfix_excelenum(hotfixType, hotfix_raw_info):    
    hotfix_code = ""
    hotfix_code += f'{_get_hotfix_log(hotfixType)}("{hotfixType} enum hotfix start")\n'

    diff_info = hotfix_raw_info['diff_info']
    for single_diff_info in diff_info:
        if single_diff_info['diff_type'] == 'modify':
            path = single_diff_info['path']
            value = single_diff_info['value']
            hotfix_code += f"Enum{_generate_hotfix_data_path(path)} = {_format_lua_value(value)}\n"
        elif single_diff_info['diff_type'] == 'add':
            path = single_diff_info['path']
            value = single_diff_info['value']
            hotfix_code += f"Enum{_generate_hotfix_data_path(path)} = {_format_lua_value(value)}\n"
        elif single_diff_info['diff_type'] == 'delete':
            path = single_diff_info['path']
            hotfix_code += f"Enum{_generate_hotfix_data_path(path)} = nil\n"
        else:
            logging.error(f"unknown diff type {single_diff_info['diff_type']}")
            return

    hotfix_code += f'{_get_hotfix_log(hotfixType)}("{hotfixType} enum hotfix end")\n'
    return hotfix_code


def generate_hotfix_exceldata(hotfixType, hotfix_raw_list):
    # hotfix_raw_list: list[hotfix_info]
    # hotfix_info
    # {    
    #     table_name: (old_data, new_data)
    #     diff_info: list[single_diff_info]
    #     is_split: bool
    # }
    # single_diff_info
    # {
    #   'diff_type': 'modify', 'add', 'delete'
    #   'path': [{str}]
    #   'value': {value}
    # }
    has_diff = False
    hotfix_code = ""
    
    all_table_name_list = []
    for hotfix_raw_info in hotfix_raw_list:
        table_name = hotfix_raw_info['table_name']
        all_table_name_list.append(table_name)

    has_string_const_data = False
    hotfix_code += f'{_get_hotfix_log(hotfixType)}("{hotfixType} excel hotfix {"___".join(all_table_name_list)} start")\n'
    for hotfix_raw_info in hotfix_raw_list:
        hotfix_code += '\n'
        table_name = hotfix_raw_info['table_name']
        local_table_name = table_name[0].lower() + table_name[1:]
        diff_info = hotfix_raw_info['diff_info']
        is_split = hotfix_raw_info['is_split']
        if table_name in ["StringConstData", "StringLuaData"]:
            has_string_const_data = True
        is_stringdb = False
        if "StringDB_CN_Data" in table_name:
            is_stringdb = True
            if hotfixType == "client":
                if table_name == "StringDB_CN_Data":
                    hotfix_code += 'local langTableName = Game.TableDataManager:GetLangTableName()\n'
                    hotfix_code += f'local table_{local_table_name} = Game.TableDataManager:GetData(langTableName)\n'
                else:
                    pattern = r'^StringDB_CN_Data(?:_(.+))?$'
                    match = re.match(pattern, table_name)
                    if match:
                        suffix = match.group(1)
                        # hotfix_code += f'local langTableName = Game.TableDataManager:GetLangTableNameByTag("{suffix}")\n'
                        hotfix_code += f'local table_{local_table_name} = (KsbcMgr.stringDBSplit and KsbcMgr.stringDBSplit["{suffix}"]) or require_data("Data.Excel.LanguageData.{table_name}").data\n'
                    else:
                        logging.error("Identify Split StringDB_CN_Data Error")

        if len(diff_info) > 0:
            has_diff = True
        
        if is_split:
            hotfix_code += f'-- 分表 {table_name} 热更，所以采用总表名\n'

        inner_hotfix_code = ""
        pre_export_hotfix_code = ""
        post_export_hotfix_code = ""
        used_key = {}
        client_use_get_table_func = False
        client_do_get_raw_table = False
        server_non_data_attr_keys = {}
        server_non_data_need_unset_raw = False
        import g
        g.diff_info = diff_info
        for single_diff_info in diff_info:
            path = single_diff_info['path']
            value = single_diff_info['value']
            if hotfixType == "client":
                lua_value_str = _format_lua_value(value)
                if is_stringdb:
                    inner_hotfix_code += f"table_{local_table_name}{_generate_hotfix_data_path(path[1:])} = {lua_value_str}\n"
                elif path[0] == "data":
                    row_key = path[1]
                    lua_row_key_str = _format_lua_value(row_key)
                    if len(single_diff_info['path']) == 2:
                        if single_diff_info['diff_type'] == 'add':
                            # Game.TableDataManager:addHotfixRowData(tableName, 666, newRowData)
                            client_use_get_table_func = True
                            inner_hotfix_code += f"Game.TableDataManager:addHotfixRowData('{table_name}', {lua_row_key_str}, {lua_value_str})\n"
                        elif single_diff_info['diff_type'] == 'delete':
                            client_use_get_table_func = True
                            inner_hotfix_code += f"Game.TableDataManager:removeHotfixRowData('{table_name}', {lua_row_key_str})\n"
                        elif single_diff_info['diff_type'] == 'modify':
                            client_do_get_raw_table = True
                            inner_hotfix_code += f'tableData[{lua_row_key_str}] = {lua_value_str}\n'
                    else:
                        # modify，同上面的module
                        client_use_get_table_func = True
                        if row_key not in used_key:
                            used_key[path[1]] = True
                            inner_hotfix_code += f"local tableRowData_{row_key} = Game.TableDataManager:getHotfixRowData('{table_name}', {lua_row_key_str})\n"
                        inner_hotfix_code += f'tableRowData_{row_key}{_generate_hotfix_data_path(path[2:])} = {lua_value_str}\n'
                else:  # attr,目前只考虑modify
                    attr_name = path[0]
                    if len(path) == 1:
                        # inner_hotfix_code += f"Game.TableDataManager:setHotfixAttrData('{table_name}', {_format_lua_value(attr_name)}, {lua_value_str})\n"
                        inner_hotfix_code += f"Game.KsbcMgr.entry['{table_name}'][{_format_lua_value(attr_name)}] = {lua_value_str}\n"
                    else:
                        if attr_name not in used_key:
                            used_key[attr_name] = True
                            inner_hotfix_code += f"local tableAttrData_{attr_name} = Game.TableDataManager:getHotfixAttrData('{table_name}', {_format_lua_value(attr_name)})\n"
                        inner_hotfix_code += f'tableAttrData_{attr_name}{_generate_hotfix_data_path(path[1:])} = {lua_value_str}\n'
            else:  # server
                if is_stringdb:
                    inner_hotfix_code += f'table_{local_table_name}{_generate_hotfix_data_path(path[1:])} = {_format_lua_value(value)}\n'
                else:
                    if single_diff_info['diff_type'] == 'modify':
                        value = single_diff_info['value']
                        if path[0] == 'data':
                            if path[1] not in used_key:
                                used_key[path[1]] = True
                            path = path[1:]
                            inner_hotfix_code += f"table_{local_table_name}{_generate_hotfix_data_path(path)} = {_format_lua_value(value)}\n"
                        else:
                            if len(path) == 1:
                                server_non_data_need_unset_raw = True
                            else:
                                server_non_data_attr_keys[path[0]] = True
                            post_export_hotfix_code += f'rawTableData.{path[0]}{_generate_hotfix_data_path(path[1:])} = {_format_lua_value(value)}\n'
                    elif single_diff_info['diff_type'] == 'add':
                        value = single_diff_info['value']
                        if path[0] == 'data':
                            if path[1] not in used_key:
                                used_key[path[1]] = False
                            if len(path[1:]) >= 2:
                                used_key[path[1]] = True
                            path = path[1:]
                            inner_hotfix_code += f"table_{local_table_name}{_generate_hotfix_data_path(path)} = {_format_lua_value(value)}\n"
                        else:
                            if len(path) == 1:
                                server_non_data_need_unset_raw = True
                            else:
                                server_non_data_attr_keys[path[0]] = True
                            post_export_hotfix_code += f'rawTableData.{path[0]}{_generate_hotfix_data_path(path[1:])} = {_format_lua_value(value)}\n'
                    elif single_diff_info['diff_type'] == 'delete':
                        if path[0] == 'data':
                            if path[1] not in used_key:
                                used_key[path[1]] = False
                            if len(path[1:]) >= 2:
                                used_key[path[1]] = True
                            path = path[1:]
                            inner_hotfix_code += f"table_{local_table_name}{_generate_hotfix_data_path(path)} = nil\n"
                        else:
                            if len(path) == 1:
                                server_non_data_need_unset_raw = True
                            else:
                                server_non_data_attr_keys[path[0]] = True
                            post_export_hotfix_code += f'rawTableData.{path[0]}{_generate_hotfix_data_path(path[1:])} = nil\n'
                    else:
                        logging.error(f"unknown diff type {single_diff_info['diff_type']}")
                        return
        if hotfixType == 'server':
            if is_stringdb:
                hotfix_code += f'local stringDbData = require_raw_data("Data.Excel.LanguageData.StringDB_CN_Data")\n'
                hotfix_code += f'local table_{local_table_name} = stringDbData.data\n'
                hotfix_code += f'make_data_table_mutable(table_{local_table_name})\n'
            else:
                hotfix_code += f'local rawTableData = require_raw_data("Data.Excel.{table_name}")\n'
                hotfix_code += f'local table_{local_table_name} = rawTableData.data\n'
                if is_split:
                    for key, ismodified in used_key.items():
                        if ismodified:
                            hotfix_code += f'make_data_table_mutable(table_{local_table_name}{_generate_hotfix_data_path([key])})\n'
                        else:
                            hotfix_code += f'table.unsetreadonly(table_{local_table_name})\n'
                else:
                    hotfix_code += f'make_data_table_mutable(rawTableData)\n'
        else:
            if client_use_get_table_func:
                pass
            if client_do_get_raw_table:
                hotfix_code += f'local tableData = Game.TableData.Get{table_name}Table()\n'

        if hotfixType == 'server' and (not is_stringdb) and is_split:
            if server_non_data_need_unset_raw:
                pre_export_hotfix_code += 'table.unsetreadonly(rawTableData)\n'
            for key in server_non_data_attr_keys:
                pre_export_hotfix_code += f'table.unsetreadonly(rawTableData.{key})\n'

        hotfix_code += pre_export_hotfix_code
        hotfix_code += inner_hotfix_code
        hotfix_code += post_export_hotfix_code
        if hotfixType == 'server':
            if is_stringdb:
                hotfix_code += f'make_data_table_immutable(table_{local_table_name})\n'
            else:
                if is_split:
                    for key, ismodified in used_key.items():
                        if ismodified:
                            hotfix_code += f'make_data_table_immutable(table_{local_table_name}{_generate_hotfix_data_path([key])})\n'
                        else:
                            hotfix_code += f'table.setreadonly(table_{local_table_name})\n'
                    for key in server_non_data_attr_keys:
                        hotfix_code += f'table.setreadonly(rawTableData.{key})\n'
                    if server_non_data_need_unset_raw:
                        hotfix_code += f'table.setreadonly(rawTableData)\n'
                else:
                    hotfix_code += f'make_data_table_immutable(rawTableData)\n'
    
    if not has_diff:
        return ''
    if hotfixType == 'client':
        if has_string_const_data:
            hotfix_code += '\n'
            hotfix_code += f'local StringConst = kg_require("Gameplay.Const.StringConst.StringConst").StringConst\n'
            hotfix_code += f'StringConst:OnPostHotfix()\n'

    hotfix_code += '\n'
    hotfix_code += f'{_get_hotfix_log(hotfixType)}("{hotfixType} excel hotfix {"___".join(all_table_name_list)} end")'
    return hotfix_code


def generate_hotfix_animlib(hotfixType, hotfix_raw_list):
    has_diff = False
    hotfix_code = ""
    
    all_table_name_list = []
    for hotfix_raw_info in hotfix_raw_list:
        table_name = hotfix_raw_info['table_name']
        all_table_name_list.append(table_name)

    hotfix_code += f'{_get_hotfix_log(hotfixType)}("{hotfixType} animlib hotfix {"___".join(all_table_name_list)} start")\n'
    hotfix_code += f'local AnimLibUtils = kg_require("Shared.Utils.AnimLibUtils")\n'

    for hotfix_raw_info in hotfix_raw_list:
        hotfix_code += '\n'
        table_name = hotfix_raw_info['table_name']
        diff_info = hotfix_raw_info['diff_info']
        old_data = hotfix_raw_info.get('old_data')
        new_data = hotfix_raw_info.get('new_data')

        if len(diff_info) > 0:
            has_diff = True
        
        inner_hotfix_code = ""
        post_export_hotfix_code = ""
        client_add_whole_part = hotfixType == 'client' and old_data in ({}, None) and new_data not in ({}, None)
        for single_diff_info in diff_info:
            if single_diff_info['diff_type'] == 'modify':
                path = single_diff_info['path']
                value = single_diff_info['value']
                if hotfixType == 'server':
                    post_export_hotfix_code += f'rawTableData.{path[0]}{_generate_hotfix_data_path(path[1:])} = {_format_lua_value(value)}\n'
                else:
                    inner_hotfix_code += f'tableAnimData{_generate_hotfix_data_path(path)} = {_format_lua_value(value)}\n'
            elif single_diff_info['diff_type'] == 'add':
                path = single_diff_info['path']
                value = single_diff_info['value']
                if hotfixType == 'server':
                    post_export_hotfix_code += f'rawTableData.{path[0]}{_generate_hotfix_data_path(path[1:])} = {_format_lua_value(value)}\n'
                elif not client_add_whole_part:
                    inner_hotfix_code += f'tableAnimData{_generate_hotfix_data_path(path)} = {_format_lua_value(value)}\n'
            elif single_diff_info['diff_type'] == 'delete':
                path = single_diff_info['path']
                if hotfixType == 'server':
                    post_export_hotfix_code += f'rawTableData.{path[0]}{_generate_hotfix_data_path(path[1:])} = nil\n'
                else:
                    inner_hotfix_code += f'tableAnimData{_generate_hotfix_data_path(path)} = nil\n'
            else:
                logging.error(f"unknown diff type {single_diff_info['diff_type']}")
                return
        if hotfixType == 'server':
            hotfix_code += f'local rawTableData = require_raw_data("Data.AnimLib.{table_name}")\n'
            hotfix_code += f'make_data_table_mutable(rawTableData)\n'
        elif client_add_whole_part:
            hotfix_code += f'Game.TableDataManager:addHotfixKsbcPartData("Anim", "{table_name}", {_format_lua_value(new_data)})\n'
        else:
            hotfix_code += f'local tableAnimData = Game.TableDataManager:getHotfixKsbcPartData("Anim", "{table_name}")\n'
        hotfix_code += inner_hotfix_code
        hotfix_code += post_export_hotfix_code
        if hotfixType == 'server':
            hotfix_code += f'make_data_table_immutable(rawTableData)\n'
            hotfix_code += f'AnimLibUtils.HotfixAnimData()\n'
    if not has_diff:
        return ''
    hotfix_code += '\n'
    hotfix_code += f'{_get_hotfix_log(hotfixType)}("{hotfixType} animlib hotfix {"___".join(all_table_name_list)} end")'
    return hotfix_code


def generate_hotfix_spacedata(hotfixType, hotfix_raw_list):
    # hotfix_raw_list: list[hotfix_info]
    # hotfix_info
    # {    
    #     is_filepath_direct: is_spacedata_direct
    #     scene_name: scene_name
    #     group_name: group_name
    #     diff_info: list[single_diff_info]
    #     old_data: old_data
    #     new_data: new_data
    # }
    # single_diff_info
    # {
    #   'diff_type': 'modify', 'add', 'delete'
    #   'path': [{str}]
    #   'value': {value}
    # }
    has_diff = False
    hotfix_code = ""
    
    all_spacedata_name_list = []
    for hotfix_raw_info in hotfix_raw_list:
        scene_name = hotfix_raw_info['scene_name']
        group_name = hotfix_raw_info['group_name']
        spacedata_name = scene_name + '/' + group_name
        all_spacedata_name_list.append(spacedata_name)
        hotfix_code += f'{_get_hotfix_log(hotfixType)}("{hotfixType} spacedata hotfix {"___".join(all_spacedata_name_list)} start")\n'

    if hotfixType == 'client':
        for hotfix_raw_info in hotfix_raw_list:
            hotfix_code += '\n'
            scene_name = hotfix_raw_info['scene_name']
            group_name = hotfix_raw_info['group_name']
            diff_info = hotfix_raw_info['diff_info']
            old_data = hotfix_raw_info['old_data']
            new_data = hotfix_raw_info['new_data']
            is_filepath_direct = hotfix_raw_info['is_filepath_direct']

            if is_filepath_direct:
                if len(diff_info) > 0:
                    has_diff = True
                hotfix_data = {}
                for single_diff_info in diff_info:
                    if single_diff_info['diff_type'] == 'modify':
                        path = single_diff_info['path']
                        value = single_diff_info['value']
                        hotfix_data[path[0]] = new_data[path[0]]
                        # inner_hotfix_code += f'{path[0]}{_generate_hotfix_data_path(path[1:])} = {_format_lua_value(value)}\n'
                    elif single_diff_info['diff_type'] == 'add':
                        path = single_diff_info['path']
                        value = single_diff_info['value']
                        hotfix_data[path[0]] = new_data[path[0]]
                        # inner_hotfix_code += f'{path[0]}{_generate_hotfix_data_path(path[1:])} = {_format_lua_value(value)}\n'
                    elif single_diff_info['diff_type'] == 'delete':
                        path = single_diff_info['path']
                        value = single_diff_info['value']
                        hotfix_data[path[0]] = "nil"
                        # inner_hotfix_code += f'{path[0]}{_generate_hotfix_data_path(path[1:])} = nil\n'
                    else:
                        logging.error(f"unknown diff type {single_diff_info['diff_type']}")
                        return
                hotfix_code += f"local space_data = {_format_lua_value(hotfix_data)}\n"
                hotfix_code += f'Game.WorldDataManager:HotfixSceneMetaData("{group_name}", space_data)\n'
            else:
                if len(diff_info) > 0:
                    has_diff = True
                is_modified = {}
                hotfix_data = {}
                for single_diff_info in diff_info:
                    if single_diff_info['diff_type'] == 'modify':
                        path = single_diff_info['path']
                        name = path[0]
                        if name in is_modified:
                            continue
                        else:
                            is_modified[name] = True
                        if "ID" in new_data[name]:
                            id = new_data[name]['ID']
                            # id = new_data[name]
                            hotfix_data[str(id)] = new_data[name]
                        else:
                            hotfix_data[name] = new_data[name]
                    elif single_diff_info['diff_type'] == 'add':
                        path = single_diff_info['path']
                        name = path[0]
                        if "ID" in new_data[name]:
                            id = new_data[name]['ID']
                            # id = new_data[name]
                            hotfix_data[str(id)] = new_data[name]
                        else:
                            hotfix_data[name] = new_data[name]
                    elif single_diff_info['diff_type'] == 'delete':
                        path = single_diff_info['path']
                        name = path[0]
                        if name in new_data and "ID" in new_data[name]:
                            id = new_data[name]['ID']
                            # id = new_data[name]
                        else:
                            id = old_data[name]['ID']
                        if len(path) == 1:
                            hotfix_data[str(id)] = "nil"
                        else:
                            hotfix_data[str(id)] = new_data[name]
                    else:
                        logging.error(f"unknown diff type {single_diff_info['diff_type']}")
                        return
                hotfix_code += f"local space_data = {_format_lua_value(hotfix_data)}\n"
                hotfix_code += f'Game.WorldDataManager:AddBatchHotfixData("{scene_name}", "{group_name}", space_data)\n'
    else:
        for hotfix_raw_info in hotfix_raw_list:
            hotfix_code += '\n'
            scene_name = hotfix_raw_info['scene_name']
            group_name = hotfix_raw_info['group_name']
            diff_info = hotfix_raw_info['diff_info']
            old_data = hotfix_raw_info['old_data']
            new_data = hotfix_raw_info['new_data']

            if len(diff_info) > 0:
                has_diff = True

            hotfix_code += f'local space_data_{group_name} = require_raw_data("Data.LogicSpaceData.{group_name}")\n'
            hotfix_code += f'make_data_table_mutable(space_data_{group_name})\n'
            for single_diff_info in diff_info:
                if single_diff_info['diff_type'] == 'modify':
                    path = single_diff_info['path']
                    value = single_diff_info['value']
                    hotfix_code += f"space_data_{group_name}{_generate_hotfix_data_path(path)} = {_format_lua_value(value)}\n"
                elif single_diff_info['diff_type'] == 'add':
                    path = single_diff_info['path']
                    value = single_diff_info['value']
                    hotfix_code += f"space_data_{group_name}{_generate_hotfix_data_path(path)} = {_format_lua_value(value)}\n"
                elif single_diff_info['diff_type'] == 'delete':
                    path = single_diff_info['path']
                    hotfix_code += f"space_data_{group_name}{_generate_hotfix_data_path(path)} = nil\n"
            hotfix_code += f'make_data_table_immutable(space_data_{group_name})\n'

    if not has_diff:
        return ''
    hotfix_code += '\n'
    hotfix_code += f'{_get_hotfix_log(hotfixType)}("{hotfixType} spacedata hotfix {"___".join(all_spacedata_name_list)} end")'
    return hotfix_code

def generate_hotfix_formula(hotfixType, hotfix_raw_list):
    hotfix_code = ""
    all_table_name_list = []
    for hotfix_raw_info in hotfix_raw_list:
        table_name = hotfix_raw_info['table_name']
        all_table_name_list.append(table_name)

    hotfix_code += f'{_get_hotfix_log(hotfixType)}("{hotfixType} formula hotfix {"___".join(all_table_name_list)} start")\n'

    head_hotfix_code = ""
    body_hotfix_code = ""

    require_info = {}
    for hotfix_raw_info in hotfix_raw_list:
        table_data_name = hotfix_raw_info['table_name']
        if hotfixType == 'server':
            runtime_name = TableName2RuntimeName[table_data_name]
            body_hotfix_code += f'local {runtime_name} = kg_require("Data.Formula.{table_data_name}").{runtime_name}\n'
            has_diff = False
            code_diff_info = hotfix_raw_info['code_diff_info']
            for single_diff_info in code_diff_info:
                if single_diff_info['code_type'] == 'my_functions':
                    if single_diff_info['diff_type'] in ['modify', 'add']:
                        name = single_diff_info['name']
                        code = single_diff_info['code']
                        body_hotfix_code += f"\n{code}\n"
                        # assign_name需要去掉前面的__
                        if name.startswith('__'):
                            assign_name = name[2:]
                        else:
                            assign_name = name  
                        body_hotfix_code += f"{runtime_name}.{assign_name} = {name}\n"
                        has_diff = True
                    elif single_diff_info['diff_type'] == 'delete':
                        pass
            if has_diff:
                cur_requires = hotfix_raw_info['new_code_visitor'].my_local_assigns
                require_info.update(cur_requires)
        else:  # client
            code_diff_info = hotfix_raw_info['code_diff_info']
            has_diff = False
            for single_diff_info in code_diff_info:
                if single_diff_info['code_type'] == 'my_functions':
                    if single_diff_info['diff_type'] in ['modify', 'add']:
                        name = single_diff_info['name']
                        code = single_diff_info['code']
                        body_hotfix_code += f"\n{code}\n"

                        body_hotfix_code += f"setfenv({name}, FormulaEnv)\n"
                        body_hotfix_code += f'FormulaEnv["{name}"] = {name}\n'
                        has_diff = True
                    elif single_diff_info['diff_type'] == 'delete':
                        pass
            if has_diff:
                cur_requires = hotfix_raw_info['new_code_visitor'].my_local_assigns
                require_info.update(cur_requires)

    for require_code in require_info.values():
        head_hotfix_code += f"{require_code}\n"

    hotfix_code += head_hotfix_code
    hotfix_code += body_hotfix_code
    hotfix_code += '\n'
    hotfix_code += f'{_get_hotfix_log(hotfixType)}("{hotfixType} formula hotfix {"___".join(all_table_name_list)} end")'
    return hotfix_code


def generate_hotfix_flowchart(hotfixType, hotfix_raw_list):
    all_table_name_list = []
    hotfix_code = ''
    for hotfix_raw_info in hotfix_raw_list:
        table_name = hotfix_raw_info['file_name']
        all_table_name_list.append(table_name)

    hotfix_code += f'{_get_hotfix_log(hotfixType)}("{hotfixType} flowchart hotfix {"___".join(all_table_name_list)} start")\n'
    
    for hotfix_raw_info in hotfix_raw_list:
        flowchart_name = hotfix_raw_info['flowchart_name']
        new_flowchart_content = hotfix_raw_info['new_flowchart_content']
        if hotfixType == 'server':
            # 寻找安全的 Lua 长字符串定界符，避免内容中包含定界符导致语法错误
            level = 1
            while True:
                equals = "=" * level
                if f"]{equals}]" not in new_flowchart_content:
                    start_delim = f"[{equals}["
                    end_delim = f"]{equals}]"
                    break
                level += 1
            hotfix_code += f"local flowchart_name = \"{flowchart_name}\"\n"
            hotfix_code += f"local new_flowchart_content = {start_delim}\n{new_flowchart_content}\n{end_delim}\n"
            hotfix_code += 'HotfixFlowchartByContent(flowchart_name, new_flowchart_content)\n'
        else:  # client
            hotfix_code += '\n'
            hotfix_code += f"HotfixFlowchartByFunction(\n"
            hotfix_code += f'\"{flowchart_name}\",\n'
            hotfix_code += "function()\n"
            hotfix_code += f"{new_flowchart_content}\n"
            hotfix_code += "end)\n"

    hotfix_code += '\n'
    hotfix_code += f'{_get_hotfix_log(hotfixType)}("{hotfixType} flowchart hotfix {"___".join(all_table_name_list)} end")'
    return hotfix_code

def generate_hotfix_combat_exceldata(hotfixType, hotfix_raw_list):
    # hotfix_raw_list: list[hotfix_info]
    # hotfix_info
    # {    
    #     table_name: (old_data, new_data)
    #     diff_info: list[single_diff_info]
    #     file_path
    #     is_split: bool
    # }

    hotfix_code = generate_hotfix_exceldata(hotfixType, hotfix_raw_list)
    if hotfix_code == '':
        return ''
    
    if hotfixType == 'client':
        return hotfix_code
    
    # 去掉最后的 print end 语句（最后一行）
    lines = hotfix_code.split('\n')
    # 找到最后一个非空行的索引
    for i in range(len(lines) - 1, -1, -1):
        log_str = _get_hotfix_log(hotfixType)
        if lines[i].strip().startswith(log_str):
            last_line = lines[i]
            lines.pop(i)
            break
    hotfix_code = '\n'.join(lines)
    
    is_hotfixed = {}
    hotfix_code += '\n------------------------------- Cpp Hotfix Start -------------------------------\n'
    hotfix_code += 'local AbManager = kg_require("Logic.Combat.Ability.AbManager")\n'
    for hotfix_raw_info in hotfix_raw_list:
        table_name = hotfix_raw_info['table_name']
        local_table_name = table_name[0].lower() + table_name[1:]
        file_path = hotfix_raw_info['file_path']
        diff_info = hotfix_raw_info['diff_info']
        combat_load_type = hotfix_raw_info['combat_load_type']

        if combat_load_type == 'CppTableLoad':
            hotfix_code += f'AbManager.GetAbManagerInstance():HotfixCppCombatTableData("{file_path}", table_{local_table_name})\n'
        elif combat_load_type == 'CppRowLoad':
            ids = '{'
            for single_diff_info in diff_info:
                path = single_diff_info['path']
                if path[0] == 'data':
                    name = path[1]
                    if name in is_hotfixed:
                        continue
                    is_hotfixed[name] = True
                    if isinstance(name, int):
                        ids += f'{name}, '
                    else:
                        ids += f'"{name}", '
            ids = ids[:-2]
            ids += '}'
            hotfix_code += f'AbManager.GetAbManagerInstance():HotfixCppCombatDataByIdList("{file_path}", {ids})\n'
        else:
            hotfix_code += "TODO Enum \n"
            # hotfix_code += f'local rawEnumData = require_raw_data("{file_path}")\n'
            # hotfix_code += f'local Enum_{local_table_name} = rawEnumData.data")\n'
            # for single_diff_info in diff_info:
            #     if single_diff_info['diff_type'] == 'modify':
            #         path = single_diff_info['path']
            #         value = single_diff_info['value']
            #         path = path[1:]
            #         hotfix_code += f"Enum_{local_table_name}{_generate_hotfix_data_path(path)} = {_format_lua_value(value)}\n"
            #     elif single_diff_info['diff_type'] == 'add':
            #         path = single_diff_info['path']
            #         value = single_diff_info['value']
            #         path = path[1:]
            #         hotfix_code += f"Enum_{local_table_name}{_generate_hotfix_data_path(path)} = {_format_lua_value(value)}\n"
            #     elif single_diff_info['diff_type'] == 'delete':
            #         path = single_diff_info['path']
            #         path = path[1:]
            #         hotfix_code += f"Enum_{local_table_name}{_generate_hotfix_data_path(path)} = nil\n"
            # loadfunc = CombatDataHotfixCfgModule.ManualHotFixDataPathName[file_path]
            # hotfix_code += f'AbManager.GetAbManagerInstance():{loadfunc}(Enum.{table_name}, true)'

    hotfix_code += '\n------------------------------- Cpp Hotfix End -------------------------------\n'
    hotfix_code += '\n'
    hotfix_code += last_line
    return hotfix_code

def generate_hotfix_questdata(hotfixType, hotfix_raw_list):
    # hotfix_raw_list: list[hotfix_info]
    # hotfix_info
    # {    
    #     table_name: (old_data, new_data)
    #     file_name: string,
    #     diff_info: list[single_diff_info]
    #     is_split: bool
    # }
    # single_diff_info
    # {
    #   'diff_type': 'modify', 'add', 'delete'
    #   'path': [{str}]
    #   'value': {value}
    # }
    has_diff = False
    hotfix_code = ""
    
    all_table_name_list = []
    for hotfix_raw_info in hotfix_raw_list:
        table_name = hotfix_raw_info['table_name']
        all_table_name_list.append(table_name)

    hotfix_code += f'{_get_hotfix_log(hotfixType)}("{hotfixType} quest hotfix {"___".join(all_table_name_list)} start")\n'
    for hotfix_raw_info in hotfix_raw_list:
        hotfix_code += '\n'
        table_name = hotfix_raw_info['table_name']
        local_table_name = table_name[0].lower() + table_name[1:]
        file_name = hotfix_raw_info['file_name'].replace("/", ".")
        diff_info = hotfix_raw_info['diff_info']
        is_split = hotfix_raw_info['is_split']

        if len(diff_info) > 0:
            has_diff = True
        
        if is_split:
            hotfix_code += f'-- 分表 {table_name} 热更，所以采用总表名\n'

        inner_hotfix_code = ""
        post_export_hotfix_code = ""
        for single_diff_info in diff_info:
            if single_diff_info['diff_type'] == 'modify':
                path = single_diff_info['path']
                value = single_diff_info['value']
                inner_hotfix_code += f"quest_{local_table_name}{_generate_hotfix_data_path(path)} = {_format_lua_value(value)}\n"
            elif single_diff_info['diff_type'] == 'add':
                path = single_diff_info['path']
                value = single_diff_info['value']
                inner_hotfix_code += f"quest_{local_table_name}{_generate_hotfix_data_path(path)} = {_format_lua_value(value)}\n"
            elif single_diff_info['diff_type'] == 'delete':
                path = single_diff_info['path']
                inner_hotfix_code += f"quest_{local_table_name}{_generate_hotfix_data_path(path)} = nil\n"
            else:
                logging.error(f"unknown diff type {single_diff_info['diff_type']}")
                return
        if hotfixType == 'server':
            hotfix_code += f'local rawQuestData = require_raw_data("{file_name}")\n'
            hotfix_code += f'make_data_table_mutable(rawQuestData)\n'
            hotfix_code += f'local quest_{local_table_name} = rawQuestData\n'
        else:
            # 获取最后的文件名"Data.Config.Quest.Ring.970003"
            file_name = file_name.split(".")[-1]
            # hotfix_code += f'local quest_{local_table_name} = Game.QuestSystem:GetRingExcelCfg({file_name})\n'
            hotfix_code += f'local quest_{local_table_name} = Game.TableDataManager:getHotfixQuestData({file_name})\n'

        hotfix_code += inner_hotfix_code
        hotfix_code += post_export_hotfix_code
        if hotfixType == 'server':
            hotfix_code += f'make_data_table_immutable(rawQuestData)\n'
    if not has_diff:
        return ''
    if hotfixType == 'client':
        hotfix_code += '\n'
        hotfix_code += f'Game.GlobalEventSystem:Publish(EEventTypesV2.QUEST_ON_LIST_UPDATE)\n'
    hotfix_code += '\n'
    hotfix_code += f'{_get_hotfix_log(hotfixType)}("{hotfixType} quest hotfix {"___".join(all_table_name_list)} end")'
    return hotfix_code

def generate_hotfix_skilldata(hotfixType, hotfix_raw_list):
    hotfix_code = ""
    
    all_table_name_list = []
    for hotfix_raw_info in hotfix_raw_list:
        table_name = hotfix_raw_info['table_name']
        all_table_name_list.append(table_name)

    has_diff = False
    is_movebyanim = False
    is_hotfixed = {}
    hotfix_code += f'{_get_hotfix_log(hotfixType)}("{hotfixType} skill hotfix {"___".join(all_table_name_list)} start")\n'
    for hotfix_raw_info in hotfix_raw_list:
        hotfix_code += '\n'
        table_name = hotfix_raw_info['table_name']
        local_table_name = table_name[0].lower() + table_name[1:]
        file_name = hotfix_raw_info['file_name'].replace("/", ".")
        diff_info = hotfix_raw_info['diff_info']
        is_split = hotfix_raw_info['is_split']

        if table_name not in is_hotfixed:
            is_hotfixed[table_name] = True
        
        if "MoveByAnim" in file_name:
            is_movebyanim = True

        if len(diff_info) > 0:
            has_diff = True
        
        if is_split:
            hotfix_code += f'-- 分表 {table_name} 热更，所以采用总表名\n'

        inner_hotfix_code = ""
        post_export_hotfix_code = ""
        used_key = {}
        for single_diff_info in diff_info:
            if single_diff_info['diff_type'] == 'modify':
                path = single_diff_info['path']
                if path[0] not in used_key:
                    used_key[path[0]] = True
                value = single_diff_info['value']
                inner_hotfix_code += f"skill_{local_table_name}{_generate_hotfix_data_path(path)} = {_format_lua_value(value)}\n"
            elif single_diff_info['diff_type'] == 'add':
                path = single_diff_info['path']
                if path[0] not in used_key:
                    used_key[path[0]] = False
                value = single_diff_info['value']
                inner_hotfix_code += f"skill_{local_table_name}{_generate_hotfix_data_path(path)} = {_format_lua_value(value)}\n"
            elif single_diff_info['diff_type'] == 'delete':
                path = single_diff_info['path']
                if path[0] not in used_key:
                    used_key[path[0]] = False
                inner_hotfix_code += f"skill_{local_table_name}{_generate_hotfix_data_path(path)} = nil\n"
            else:
                logging.error(f"unknown diff type {single_diff_info['diff_type']}")
                return
        if hotfixType == 'server':
            if is_movebyanim:
                file_name = file_name.replace(".", "/")
                hotfix_code += f'kg_require("{file_name}")\n'
                hotfix_code += f'local skill_{local_table_name} = _G.ASASMoveByAnim[{table_name}]\n'
            else:
                hotfix_code += f'local rawSkillData = require_raw_data("{file_name}")\n'
                hotfix_code += f'local skill_{local_table_name} = rawSkillData\n'
            # 分表及有part表的特殊处理
            if "Ability" in file_name:
                for key, ismodified in used_key.items():
                    if ismodified:
                        hotfix_code += f'make_data_table_mutable(skill_{local_table_name}{_generate_hotfix_data_path([key])})\n'
                    else:
                        hotfix_code += f'table.unsetreadonly(skill_{local_table_name})\n'
            else:
                hotfix_code += f'make_data_table_mutable(skill_{local_table_name})\n'
        else:
            if "AbilitySystem.SkillData" in file_name:
                hotfix_code += f'local skill_{local_table_name} = kg_require("Data.Config.BattleSystem.{file_name}").Data\n'
            elif "AbilitySystem.Skill" in file_name:
                hotfix_code += f'local skill_{local_table_name} = Game.CombatDataManager:GetAbilityDT({table_name})\n'
            elif "AbilitySystem.EffectSkill" in file_name:
                hotfix_code += f'local skill_{local_table_name} = Game.CombatDataManager:GetEffectSkillDT({table_name})\n'

        hotfix_code += inner_hotfix_code
        hotfix_code += post_export_hotfix_code
        if hotfixType == 'server':
            if is_movebyanim:
                hotfix_code += 'local AbManager = kg_require("Logic.Combat.Ability.AbManager")\n'
                hotfix_code += 'local skillIdMap = {}\n'
                for name in is_hotfixed:
                    hotfix_code += f'skillIdMap[{name}] = true\n'
                hotfix_code += f'AbManager:HotfixAnimDataNew(skillIdMap)\n'
            elif "Ability" in file_name:
                hotfix_code += 'local AbManager = kg_require("Logic.Combat.Ability.AbManager")\n'
                ids = '{'
                is_used = {}
                for single_diff_info in diff_info:
                    path = single_diff_info['path']
                    name = path[0]
                    if name in is_used:
                        continue
                    is_used[name] = True
                    if isinstance(name, int):
                        ids += f'{name}, '
                    else:
                        ids += f'"{name}", '
                if ids != "{":
                    ids = ids[:-2]
                    ids += '}'
                    hotfix_code += f'AbManager.GetAbManagerInstance():HotfixCppCombatDataByIdList("{file_name}", {ids})\n'
            if "Ability" in file_name:
                for key, ismodified in used_key.items():
                    if ismodified:
                        hotfix_code += f'make_data_table_immutable(skill_{local_table_name}{_generate_hotfix_data_path([key])})\n'
                    else:
                        hotfix_code += f'table.setreadonly(skill_{local_table_name})\n'
            else:
                hotfix_code += f'make_data_table_immutable(skill_{local_table_name})\n'
        else:
            hotfix_code += f'Game.DataCacheManager:CleanCache()'
    if not has_diff:
        return ''
    hotfix_code += '\n'

    hotfix_code += f'{_get_hotfix_log(hotfixType)}("{hotfixType} skill hotfix {"___".join(all_table_name_list)} end")'
    return hotfix_code

# from Implement.hotfixImpl import luaImp
# luaImp.test_hotfix()
# old_path = '/app/p4WorkSpace/Mainline/Server/script_lua/tmp/Data/Excel/FStatePropDataOld.lua'
# new_path = '/app/p4WorkSpace/Mainline/Server/script_lua/tmp/Data/Excel/FStatePropDataNew.lua'

def _check_file_type(file_name):
    if re.search(r'/Client/Content/Script/(Data|Gameplay/Formula)/([^#]*)\.lua', file_name, re.IGNORECASE):
        return 'client'
    elif re.search(r'/Server/script_lua/Data/([^#]*)\.lua', file_name, re.IGNORECASE):
        return 'server'
    else:
        return ''

def check_hotfix_type(hotfixPrepareInfo):
    has_client = False
    has_server = False
    for hotfixInfo in hotfixPrepareInfo:
        raw_file_name = hotfixInfo['rawFilePath']
        if _check_file_type(raw_file_name) == 'client':
            has_client = True
        elif _check_file_type(raw_file_name) == 'server':
            has_server = True
        else:
            logging.error(f"two files in different formats cannot be compared")
            return ""
    if has_client and has_server:
        return "both"
    elif has_client:
        return "client"
    elif has_server:
        return "server"
    else:
        return ""

def generate_hotfix_by_content(hotfixType, hotfixPrepareInfo):
    hotfix_animlib_info = []
    hotfix_exceldata_info = []
    hotfix_formula_info = []
    hotfix_skilldata_info = []
    hotfix_combat_exceldata_info = []
    hotfix_excelenum_info = []
    hotfix_spacedata_info = []
    hotfix_flowchart_info = []
    hotfix_quest_info = []
    for hotfixInfo in hotfixPrepareInfo:
        raw_file_name = hotfixInfo['rawFilePath']
        # 如果符合黑名单路径规则的文件，则跳过
        if _is_blacklisted_raw_file_path(raw_file_name):
            logging.warning(f"skip blacklisted file: {raw_file_name}")
            continue

        if check_combat_exceldata(raw_file_name, hotfixInfo):
            hotfix_combat_exceldata_info.append(hotfixInfo)
            continue
        if re.search(r'/SpaceData/([^#]*)\.lua', raw_file_name, re.IGNORECASE) \
        or re.search(r'/LogicSpaceData/([^#]*)\.lua', raw_file_name, re.IGNORECASE):
            hotfix_spacedata_info.append(hotfixInfo)
        elif re.search(r'/Excel/([^#]*)\.lua', raw_file_name, re.IGNORECASE):
            if "/ExcelEnum.lua" in raw_file_name:
                hotfix_excelenum_info.append(hotfixInfo)
            else:
                hotfix_exceldata_info.append(hotfixInfo)
        elif re.search(r'/AnimLib/([^#]*)\.lua', raw_file_name, re.IGNORECASE) \
        or re.search(r'/Data/Config/Anim/([^#]*)\.lua', raw_file_name, re.IGNORECASE):
            hotfix_animlib_info.append(hotfixInfo)
        elif re.search(r'/Formula/([^#]*)\.lua', raw_file_name, re.IGNORECASE): 
            hotfix_formula_info.append(hotfixInfo)
        elif re.search(r'/Flowchart/([^#]*)\.lua', raw_file_name, re.IGNORECASE):
            hotfix_flowchart_info.append(hotfixInfo)
        elif re.search(r'/Quest/([^#]*)\.lua', raw_file_name, re.IGNORECASE):
            hotfix_quest_info.append(hotfixInfo)
        elif re.search(r'/SkillData/([^#]*)\.lua', raw_file_name, re.IGNORECASE) \
        or re.search(r'/Skill/([^#]*)\.lua', raw_file_name, re.IGNORECASE) or re.search(r'/EffectSkill/([^#]*)\.lua', raw_file_name, re.IGNORECASE):
            hotfix_skilldata_info.append(hotfixInfo)
        else:
            logging.error(f"two files in different formats cannot be compared, {raw_file_name}")
            return f'return "暂不支持该格式: {raw_file_name}"', []

    # 收集所有的 raw_list，用于后续生成 diff tags
    all_raw_lists = []

    if hotfix_quest_info:
        hotfix_questdata_content, questdata_raw_list = generate_questdata_hotfix_content(hotfixType, hotfix_quest_info)
        all_raw_lists.extend(questdata_raw_list)
    else:
        hotfix_questdata_content = ''
    if hotfix_exceldata_info:
        # 这里要把StringDB_CN_Data相关的剔除掉
        hotfix_exceldata_info = [x for x in hotfix_exceldata_info if not re.search(r'StringDB_CN_Data(_.*)?\.lua', x['rawFilePath'], re.IGNORECASE)]
        hotfix_exceldata_content, exceldata_raw_list = generate_exceldata_hotfix_content(hotfixType, hotfix_exceldata_info)
        all_raw_lists.extend(exceldata_raw_list)
    else:
        hotfix_exceldata_content = ''
    if hotfix_excelenum_info:
        hotfix_excelenum_content, excelenum_raw_list = generate_excelenum_hotfix_content(hotfixType, hotfix_excelenum_info)
        all_raw_lists.extend(excelenum_raw_list)
    else:
        hotfix_excelenum_content = ''
    if hotfix_animlib_info:
        hotfix_animlib_content, animlib_raw_list = generate_animlib_hotfix_content(hotfixType, hotfix_animlib_info)
        all_raw_lists.extend(animlib_raw_list)
    else:
        hotfix_animlib_content = ''
    if hotfix_formula_info:
        hotfix_formula_content, formula_raw_list = generate_formula_hotfix_content(hotfixType, hotfix_formula_info)
        all_raw_lists.extend(formula_raw_list)
    else:
        hotfix_formula_content = ''
    if hotfix_spacedata_info:
        hotfix_spacedata_content, spacedata_raw_list = generate_spacedata_hotfix_content(hotfixType, hotfix_spacedata_info)
        all_raw_lists.extend(spacedata_raw_list)
    else:
        hotfix_spacedata_content = ''
    if hotfix_flowchart_info:
        hotfix_flowchart_content, flowchart_raw_list = generate_flowchart_hotfix_content(hotfixType, hotfix_flowchart_info)
        all_raw_lists.extend(flowchart_raw_list)
    else:
        hotfix_flowchart_content = ''
    if hotfix_skilldata_info:
        hotfix_skilldata_content, skilldata_raw_list = generate_skilldata_hotfix_content(hotfixType, hotfix_skilldata_info)
        all_raw_lists.extend(skilldata_raw_list)
    else:
        hotfix_skilldata_content = ''
    if hotfix_combat_exceldata_info:
        hotfix_combat_exceldata_content, combat_exceldata_raw_list = generate_combat_exceldata_hotfix_content(hotfixType, hotfix_combat_exceldata_info)
        all_raw_lists.extend(combat_exceldata_raw_list)
    else:
        hotfix_combat_exceldata_content = ''
    hotfix_content_list = []
    for content in [hotfix_exceldata_content, hotfix_excelenum_content, hotfix_animlib_content, hotfix_formula_content, \
                    hotfix_spacedata_content, hotfix_flowchart_content, hotfix_combat_exceldata_content, \
                    hotfix_questdata_content, hotfix_skilldata_content]:
        if content.strip() == '':
            continue
        hotfix_content_list.append(content)
    hotfix_content = '\n\n'.join(hotfix_content_list)
    
    # 直接执行文件来检查不太行，lua环境里没有getxxx之类的函数
    lua_env = LuaEnv()
    lua_env.check_lua_content(hotfix_content)

    # result = aiImp.aiRequest(f'帮我看下这里的lua代码有没有可以优化的地方\n{hotfix_content}')
    # logging.info(f'ai返回结果：{result}')
    return hotfix_content, all_raw_lists


def generate_animlib_hotfix_content(hotfixType, hotfix_animlib_info):
    hotfix_raw_list = []
    for hotfixInfo in hotfix_animlib_info:
        raw_file_name = hotfixInfo['rawFilePath']
        old_file_name = hotfixInfo['oldFilePath']
        new_file_name = hotfixInfo['newFilePath']
        old_content = hotfixInfo['oldFileContent']
        new_content = hotfixInfo['newFileContent']
        table_data_name, is_split = p4Utils.get_table_data_name(raw_file_name)
        lua_env = LuaEnv()
        lua_env.prepare_env()
        data1 = lua_env.load_lua_content(old_content, old_file_name) # data1是python dict
        data2 = lua_env.load_lua_content(new_content, new_file_name) # data2是python dict
        diff_info = _compare_dict(old_dict=data1, new_dict=data2, path=[])
        logging.info(f"czx animlib generate_diff success {diff_info}")
        hotfix_raw_list.append({
            'table_name': table_data_name,
            'diff_info': diff_info,
            'raw_file_path': raw_file_name,
            'is_split': is_split,
            'old_data': data1,
            'new_data': data2,
        })
    return generate_hotfix_animlib(hotfixType, hotfix_raw_list), hotfix_raw_list


def generate_formula_hotfix_content(hotfixType, hotfix_formula_info):
    hotfix_raw_list = []
    for hotfixInfo in hotfix_formula_info:
        raw_file_name = hotfixInfo['rawFilePath']
        old_file_name = hotfixInfo['oldFilePath']
        old_content = hotfixInfo['oldFileContent']
        new_content = hotfixInfo['newFileContent']
        table_data_name, _ = p4Utils.get_table_data_name(raw_file_name)
        analyzer1 = luaParserImp.analyze_lua_code(old_content)
        analyzer2 = luaParserImp.analyze_lua_code(new_content)
        code_diff_info = luaParserImp._compare_code(analyzer1, analyzer2)

        logging.info(f"czx formula generate_diff success {code_diff_info}")
        hotfix_raw_list.append({
            'table_name': table_data_name,
            'code_diff_info': code_diff_info,
            'new_code_visitor': analyzer2
        })
    return generate_hotfix_formula(hotfixType, hotfix_raw_list), hotfix_raw_list


def generate_excelenum_hotfix_content(hotfixType, hotfix_excelenum_info):
    hotfixInfo = hotfix_excelenum_info[0]
    raw_file_name = hotfixInfo['rawFilePath']
    old_file_name = hotfixInfo['oldFilePath']
    new_file_name = hotfixInfo['newFilePath']
    old_content = hotfixInfo['oldFileContent']
    new_content = hotfixInfo['newFileContent']
    table_data_name, is_split = p4Utils.get_table_data_name(raw_file_name)
    lua_env = LuaEnv()
    lua_env.prepare_env()
    
    data1 = lua_env.load_lua_content(old_content, old_file_name, "Enum") # data1是python dict
    data2: list[list[Any] | dict[Any, list[Any] | dict[Any, Any] | Any] | Any] | dict[Any, Any] | Any | list[list[Any] | dict[Any, Any] | Any] = lua_env.load_lua_content(new_content, new_file_name, "Enum") # data2是python dict
    diff_info = _compare_dict(data1, data2, [])
    logging.info(f"jyd test excelenum generate_diff success {diff_info}")
    hotfix_raw_info = {
        'table_name': table_data_name,
        'diff_info': diff_info,
        'is_split': is_split,
        'new_data': data2,
    }
    return generate_hotfix_excelenum(hotfixType, hotfix_raw_info), [hotfix_raw_info]


def generate_exceldata_hotfix_content(hotfixType, hotfix_exceldata_info):
    hotfix_raw_list = []
    for hotfixInfo in hotfix_exceldata_info:
        raw_file_name = hotfixInfo['rawFilePath']
        old_file_name = hotfixInfo['oldFilePath']
        new_file_name = hotfixInfo['newFilePath']
        old_content = hotfixInfo['oldFileContent']
        new_content = hotfixInfo['newFileContent']
        table_data_name, is_split = p4Utils.get_table_data_name(raw_file_name)
        lua_env = LuaEnv()
        lua_env.prepare_env()
        
        data1 = lua_env.load_lua_content(old_content, old_file_name) # data1是python dict
        data2 = lua_env.load_lua_content(new_content, new_file_name) # data2是python dict
        diff_info = _compare_dict(data1, data2, [])
        logging.info(f"jyd test exceldata generate_diff success {diff_info}")
        hotfix_raw_list.append({
            'table_name': table_data_name,
            'diff_info': diff_info,
            'raw_file_path': raw_file_name,
            'is_split': is_split,
            'new_data': data2,
        })
    return generate_hotfix_exceldata(hotfixType, hotfix_raw_list), hotfix_raw_list

def _is_spacedata_root_file(raw_file_path):
    normalized_path = str(raw_file_path or '').replace('\\', '/')
    return bool(re.search(r'(?:^|/)SpaceData/[^/]+\.lua(?:#\d+)?$', normalized_path, re.IGNORECASE))

def _is_spacedata_root_allowed_file(raw_file_path):
    parsed_path = p4Utils.parse_p4_path(raw_file_path)
    if not isinstance(parsed_path, dict):
        return False

    file_name = str(parsed_path.get('name', '') or '')
    if not file_name:
        return False
    
    _SPACEDATA_ROOT_ALLOWED_PREFIXES = [
        'NodeLevelInfo',
        'NodeParentInfo',
        'NpcTemplateID2InsID',
        'ChairArtsTemplateDataNew',
        'ChairArtsTemplateData',
        'TransportTemplateData',
        'SpaceStaticData',
    ]

    return any(file_name.startswith(prefix) for prefix in _SPACEDATA_ROOT_ALLOWED_PREFIXES)

def generate_spacedata_hotfix_content(hotfixType, hotfix_spacedata_info):
    hotfix_raw_list = []
    for hotfixInfo in hotfix_spacedata_info:
        raw_file_path = hotfixInfo["rawFilePath"]
        old_file_name = hotfixInfo['oldFilePath']
        new_file_name = hotfixInfo['newFilePath']
        old_content = hotfixInfo['oldFileContent']
        new_content = hotfixInfo['newFileContent']
        scene_name, group_name = p4Utils.get_space_data_name(raw_file_path)
        lua_env = LuaEnv()
        lua_env.prepare_env()
        is_spacedata_direct = _is_spacedata_root_file(raw_file_path)
        if is_spacedata_direct and not _is_spacedata_root_allowed_file(raw_file_path):
            return f"暂不支持这些文件的hotfix: {raw_file_path}", []
        logging.info(f"jyd test spacedata filePath {raw_file_path}, is spacedata direct {is_spacedata_direct}")
        logging.info(f"jyd test spacedata scene name {scene_name}, group name {group_name}")
        data1 = lua_env.load_lua_content(old_content, old_file_name) # data1是python dict
        data2 = lua_env.load_lua_content(new_content, new_file_name) # data2是python dict
        diff_info = _compare_dict(data1, data2, [])
        logging.info(f"jyd test spacedata generate_diff success {diff_info}")
        hotfix_raw_list.append({
            "is_filepath_direct": is_spacedata_direct,
            'scene_name': scene_name,
            'group_name': group_name,
            'raw_file_path': raw_file_path,
            'diff_info': diff_info,
            'old_data': data1,
            'new_data': data2
        })
    
    return generate_hotfix_spacedata(hotfixType, hotfix_raw_list), hotfix_raw_list

def update_flowchart_name_file(branch_name):
    if branch_name == "mainline":
        flowchartNameFile = "//C7/Development/Mainline/Server/script_lua/Data/Flowchart/FileNameToFlowchartName.txt"
    else:
        flowchartNameFile = f"//C7/Development/Weekly/Server/script_lua/Data/Flowchart/FileNameToFlowchartName.txt"

    localFlowchartNameFile = os.path.join(config.P4_WORKSPACE_DIRECTORY, flowchartNameFile.replace("//", ""))
    # localFlowchartNameFile = "./FileNameToFlowchartName.txt"
    ret = p4Utils.update_file(flowchartNameFile, localFlowchartNameFile, force = True)
    if not ret:
        logging.error("update flowchart name file failed")
        return ""
    
    with open(localFlowchartNameFile, "r", encoding="utf-8") as f:
        content = f.read()
        logging.info("update flowchart name file success")
        return content
    
def get_flowchart_name(flowchart_name_content, file_name):
    # flowchart_name_content的内容如下：
    # Flowchart_AI_MinDragon_AI.lua AI.MinDragon_AI
    # Flowchart_AI_Monster_SimpleAI.lua AI.Monster_SimpleAI
    # Flowchart_AI_NewUnit.lua AI.NewUnit
    # Flowchart_AI_npc_test.lua AI.npc_test
    # Flowchart_AI_rose_jason_test.lua AI.rose_jason_test
    # Flowchart_AI_test4.lua AI.test4
    # Flowchart_AI_test_dialog.lua AI.test_dialog
    # file_name是类似这种：Flowchart_AI_MinDragon_AI 或者带路径 /path/to/Flowchart_AI_MinDragon_AI.lua
    # 从flowchart_name_content中提取出file_name对应的flowchart_name
    
    # 1. 处理传入的 file_name，只保留基础文件名（不含扩展名）
    # 如果 file_name 包含路径，先去掉路径
    base_name = os.path.basename(file_name)
    # 如果包含 .lua 后缀，去掉它
    if base_name.endswith('.lua'):
        base_name = base_name[:-4]
    lines = flowchart_name_content.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            # content_file_name 通常带有 .lua 后缀，如 Flowchart_AI_MinDragon_AI.lua
            content_file_name = parts[0]
            flowchart_name = parts[1]
            
            # 处理 content_file_name，去掉 .lua 后缀以便比较
            content_base_name = content_file_name
            if content_base_name.endswith('.lua'):
                content_base_name = content_base_name[:-4]
            if content_base_name == base_name:
                return flowchart_name
    return ""

def generate_flowchart_hotfix_content(hotfixType, hotfix_flowchart_info):
    if not hotfix_flowchart_info:
        return ""
    hotfix_raw_list = []
    branch_name = "mainline"
    for hotfixInfo in hotfix_flowchart_info:
        old_file_name = hotfixInfo['oldFilePath']
        if "Mainline" in old_file_name:
            branch_name = "mainline"
            break
        if "Weekly" in old_file_name:
            branch_name = "weekly"
            break
    flowchart_name_content = update_flowchart_name_file(branch_name)
    if not flowchart_name_content:
        logging.error("update flowchart name file failed")
        return ""
    for hotfixInfo in hotfix_flowchart_info:
        raw_file_name = hotfixInfo['rawFilePath']
        # new_file_name = hotfixInfo['newFilePath']
        # old_content = hotfixInfo['oldFileContent']
        new_content = hotfixInfo['newFileContent']
        flowchart_file_name, _ = p4Utils.get_table_data_name(raw_file_name)
        flowchart_name = get_flowchart_name(flowchart_name_content, flowchart_file_name)
        if not flowchart_name:
            logging.error(f"get flowchart name failed, file_name: {raw_file_name}")
            continue
        else:
            logging.info(f"generate_flowchart_hotfix_content, flowchart_name: {flowchart_name}")
        hotfix_raw_list.append({
            'file_name': flowchart_file_name,
            'flowchart_name': flowchart_name,
            'new_flowchart_content': new_content,
        })
    return generate_hotfix_flowchart(hotfixType, hotfix_raw_list), hotfix_raw_list

def get_combat_file_name(file_path):
    file_path = file_path.replace('\\', '/')
    if '#' in file_path:
        file_path = file_path.split('#')[0]
    file_path = os.path.splitext(file_path)[0]
    data_patterns = ["Data/Excel/", "Enum/"]

    for pattern in data_patterns:
        if pattern in file_path:
            idx = file_path.find(pattern)
            if idx != -1:
                file_name = file_path[idx:]
                return file_name
    return None

def check_combat_exceldata(raw_file_name, hotfixInfo):
    file_name = get_combat_file_name(raw_file_name)
    table_data_name, is_split = p4Utils.get_table_data_name(raw_file_name)
    if is_split:
        file_name = f'Data/Excel/{table_data_name}'

    if file_name == None:
        return False

    cfg = CombatDataHotfixCfgModule
    in_row = file_name in getattr(cfg, 'DataPathName2CppRowLoadfuncName', {})
    in_table = file_name in getattr(cfg, 'DataPathName2CppTableLoadfuncName', {})
    in_manual = file_name in getattr(cfg, 'ManualHotFixDataPathName', {})

    if in_row or in_table or in_manual:
        file_name = file_name.replace('/', '.')
        hotfixInfo['filePath'] = file_name
        if in_row:
            hotfixInfo['combatLoadType'] = "CppRowLoad"
        elif in_table:
            hotfixInfo['combatLoadType'] = "CppTableLoad"
        elif in_manual:
            hotfixInfo['combatLoadType'] = "CppManualLoad"
        return True
    else:
        # logging.info(f"excel file {file_name} not in combat_data_hotfix_config, skipping")
        return False

def generate_combat_exceldata_hotfix_content(hotfixType, hotfix_combat_exceldata_info):
    hotfix_raw_list = []

    split_groups = {}
    single_items = []

    for hotfixInfo in hotfix_combat_exceldata_info:
        raw_file_name = hotfixInfo['rawFilePath']
        old_file_name = hotfixInfo['oldFilePath']
        new_file_name = hotfixInfo['newFilePath']
        old_content = hotfixInfo['oldFileContent']
        new_content = hotfixInfo['newFileContent']
        file_path = hotfixInfo['filePath']
        combat_load_type = hotfixInfo['combatLoadType']
        table_data_name, is_split = p4Utils.get_table_data_name(raw_file_name)

        item = {
            'raw_file_name': raw_file_name,
            'old_file_name': old_file_name,
            'new_file_name': new_file_name,
            'old_content': old_content,
            'new_content': new_content,
            'file_path': file_path,
            'combat_load_type': combat_load_type,
            'table_data_name': table_data_name,
            'is_split': is_split,
        }

        if is_split:
            group = split_groups.get(table_data_name)
            if group is None:
                group = {
                    'table_data_name': table_data_name,
                    'file_path': file_path,
                    'combat_load_type': combat_load_type,
                    'items': [],
                }
                split_groups[table_data_name] = group
            if not group.get('file_path') and file_path:
                group['file_path'] = file_path
            if not group.get('combat_load_type') and combat_load_type:
                group['combat_load_type'] = combat_load_type
            group['items'].append(item)
        else:
            single_items.append(item)

    for group in split_groups.values():
        table_data_name = group['table_data_name']
        file_path = group.get('file_path')
        combat_load_type = group.get('combat_load_type')
        lua_env = LuaEnv()
        lua_env.prepare_env()

        merged_old = {}
        merged_new = {}
        logging.info(f"czx merge split combat excel data {table_data_name} {file_path}")
        for item in sorted(group['items'], key=lambda x: x['raw_file_name'] or ''):
            data1 = lua_env.load_lua_content(item['old_content'], item['old_file_name'])
            data2 = lua_env.load_lua_content(item['new_content'], item['new_file_name'])
            merged_old = _merge_lua_loaded_data(merged_old, data1)
            merged_new = _merge_lua_loaded_data(merged_new, data2)

        diff_info = _compare_dict(merged_old, merged_new, [])
        hotfix_raw_list.append({
            'table_name': table_data_name,
            'diff_info': diff_info,
            'file_path': file_path,
            'raw_file_path': file_path,
            'combat_load_type': combat_load_type,
            'is_split': True,
            'new_data': merged_new,
        })

    for item in single_items:
        table_data_name = item['table_data_name']
        file_path = item['file_path']
        combat_load_type = item['combat_load_type']
        lua_env = LuaEnv()
        lua_env.prepare_env()
        data1 = lua_env.load_lua_content(item['old_content'], item['old_file_name'])
        data2 = lua_env.load_lua_content(item['new_content'], item['new_file_name'])
        diff_info = _compare_dict(data1, data2, [])
        hotfix_raw_list.append({
            'table_name': table_data_name,
            'diff_info': diff_info,
            'file_path': file_path,
            'raw_file_path': file_path,
            'combat_load_type': combat_load_type,
            'is_split': False,
            'new_data': data2,
        })
    return generate_hotfix_combat_exceldata(hotfixType, hotfix_raw_list), hotfix_raw_list

def get_quest_file_name(file_path):
    file_path = file_path.replace('\\', '/')
    if '#' in file_path:
        file_path = file_path.split('#')[0]
    file_path = os.path.splitext(file_path)[0]
    data_patterns = ["Data/Quest/ExtraData", "Data/Quest/Ring", "Data/Config/Quest/Ring"]

    for pattern in data_patterns:
        if pattern in file_path:
            idx = file_path.find(pattern)
            if idx != -1:
                file_name = file_path[idx:]
                return file_name
    return None

def generate_questdata_hotfix_content(hotfixType, hotfix_questdata_info):
    hotfix_raw_list = []
    for hotfixInfo in hotfix_questdata_info:
        raw_file_name = hotfixInfo['rawFilePath']
        old_file_name = hotfixInfo['oldFilePath']
        new_file_name = hotfixInfo['newFilePath']
        old_content = hotfixInfo['oldFileContent']
        new_content = hotfixInfo['newFileContent']
        file_name = get_quest_file_name(raw_file_name)
        table_data_name, is_split = p4Utils.get_table_data_name(raw_file_name)
        logging.info(f"jyd test questdata generate {table_data_name}")
        lua_env = LuaEnv()
        lua_env.prepare_env()
        data1 = lua_env.load_lua_content(old_content, old_file_name) # data1是python dict
        data2 = lua_env.load_lua_content(new_content, new_file_name) # data2是python dict
        logging.info(f"jyd test questdata generate {table_data_name}, old_data:{data1}, new_data:{data2}")
        diff_info = _compare_dict(data1, data2, [])
        logging.info(f"jyd test questdata generate_diff success {len(diff_info)} {diff_info}")
        hotfix_raw_list.append({
            'table_name': table_data_name,
            'file_name': file_name,
            'diff_info': diff_info,
            'raw_file_path': raw_file_name,
            'is_split': is_split,
        })
    return generate_hotfix_questdata(hotfixType, hotfix_raw_list), hotfix_raw_list

def get_skill_file_name(file_path):
    file_path = file_path.replace('\\', '/')
    if '#' in file_path:
        file_path = file_path.split('#')[0]
    file_path = os.path.splitext(file_path)[0]
    data_patterns = ["Data/SkillData", "AbilitySystem/Skill", "AbilitySystem/SkillData", "AbilitySystem/EffectSkill"]

    for pattern in data_patterns:
        if pattern in file_path:
            idx = file_path.find(pattern)
            if idx != -1:
                file_name = file_path[idx:]
                return file_name
    return None

def generate_skilldata_hotfix_content(hotfixType, hotfix_skilldata_info):
    hotfix_raw_list = []
    for hotfixInfo in hotfix_skilldata_info:
        raw_file_name = hotfixInfo['rawFilePath']
        old_file_name = hotfixInfo['oldFilePath']
        new_file_name = hotfixInfo['newFilePath']
        old_content = hotfixInfo['oldFileContent']
        new_content = hotfixInfo['newFileContent']
        file_name = get_skill_file_name(raw_file_name)
        table_data_name, is_split = p4Utils.get_table_data_name(raw_file_name)
        if file_name and "Data/SkillData/Ability" in file_name:
            file_name = "Data/SkillData/AbilityDataAll"
            table_data_name = "AbilityDataAll"
        elif file_name and "AbilitySystem/SkillData/AbilityDataAll_Part" in file_name:
            file_name = "AbilitySystem/SkillDataMerge/AbilityDataAll"
            table_data_name = "AbilityDataAll"
        elif file_name and "AbilitySystem/SkillData/EffectSkillAll_Part" in file_name:
            file_name = "AbilitySystem/SkillDataMerge/EffectSkillAll"
            table_data_name = "EffectSkillAll"
        logging.info(f"jyd test skilldata generate {file_name} {table_data_name}")
        lua_env = LuaEnv()
        lua_env.prepare_env()
        data1 = lua_env.load_lua_content(old_content, old_file_name) # data1是python dict
        data2 = lua_env.load_lua_content(new_content, new_file_name) # data2是python dict
        logging.info(f"jyd test skilldata generate {table_data_name}, old_data:{data1}, new_data:{data2}")
        diff_info = _compare_dict(data1, data2, [])
        logging.info(f"jyd test skilldata generate_diff success {len(diff_info)} {diff_info}")
        hotfix_raw_list.append({
            'table_name': table_data_name,
            'diff_info': diff_info,
            'file_name': file_name,
            'raw_file_path': raw_file_name,
            'is_split': is_split,
        })
    return generate_hotfix_skilldata(hotfixType, hotfix_raw_list), hotfix_raw_list

# from Implement.hotfixImpl import luaImp
# lua_env = luaImp.LuaEnv()
# lua_env.prepare_env()
# with open(server_file_path, 'r', encoding='utf-8') as f:
# file_content = f.read() 
# data1 = lua_env.load_lua_content(file_content , "xxx")
