# -*- coding: utf-8 -*-
import copy
from code import InteractiveConsole
from io import StringIO
import sys
from typing import List
import math
import logging as _logger
import config


# 控制字符
DONT = bytes([254])
DO = bytes([253])
WILL = bytes([251])
WONT = bytes([252])
ECHO = bytes([1])  # echo
SGA = bytes([3])  # suppress go ahead
LINEMODE = bytes([34])  # Linemode option

# 输入字符
SUB = bytes([26])  # ctrl+z
SOH = bytes([1])   # ctrl+a
TB = bytes([23])  # ctrl+w
ESC = bytes([27])  # esc
BSP = bytes([8])  # backspace
DEL = bytes([127])  # delete
SE = bytes([240])  # Subnegotiation End
NOP = bytes([241])  # No Operation
SB = bytes([250])  # Subnegotiation Begin
TAB = bytes([9])
BELL = bytes([7])
NOOPT = bytes([0])
TTYPE = bytes([24])  # terminal type
IAC = bytes([255])
# Codes used in SB SE data stream for terminal type negotiation
IS = bytes([0])
SEND = bytes([1])
DEFAULT = -1    # default

# region custom_configure
# ProjectCustom 项目自己编写需要的预加载指令
# 预加载指令可以填写在这里，按行区分
PRE_INPUT_STRS = [  # telnet预加载指令
    'from console.ConsoleEnv import *',
    'from tools import globaldata',
    'import g',
    'import config',
    'from utility import const',
    'from myUnitTest import testP4',
    'from myUnitTest import testLua',
    'from Implement.aiImpl import aiImp',
    'from Implement.hotfixImpl import luaParserImp',
    'from Implement.hotfixImpl import luaImp',
]

HISTORY_MAX = 30  # 最大行历史记录，用于上下键
EDIT_HISTORY_MAX = 30  # 最大的编辑历史记录，用于Ctrl+Z撤销

AUTOCOMPLETE_WORLDS_INLINE = 4  # 每行展示的自动补全候选词
AUTOCOMPLETE_DISPLAY_MAX = 20  # 最多展示的候选词数量
AUTOCOMPLETE_MAX_LINES = math.ceil(AUTOCOMPLETE_DISPLAY_MAX / AUTOCOMPLETE_WORLDS_INLINE)
AUTOCOMPLETE_WORD_SPACING = 5  # 候选词之间的间隔空格数

QUIT_FLAGS = ['quit', 'quit()', 'exit', 'exit()']

EASTER_EGGS_TRIGGER_WORDS = [b'eggs']  # 彩蛋触发词

# 彩蛋标识
EASTER_EGGS_DISPLAY = [
    """                                                                      """,  # noqa
    """   ,----..                                           ,--,             """,  # noqa
    """  /   /   \                                        ,--.'|             """,  # noqa
    """ |   :     :  ,---.       ,---,              ,---. |  | :             """,  # noqa
    """ .   |  ;. / '   ,'\  ,-+-. /  | .--.--.    '   ,'\:  : '             """,  # noqa
    """ .   ; /--` /   /   |,--.'|'   |/  /    '  /   /   |  ' |     ,---.   """,  # noqa
    """ ;   | ;   .   ; ,. |   |  ,"' |  :  /`./ .   ; ,. '  | |    /     \  """,  # noqa
    """ |   : |   '   | |: |   | /  | |  :  ;_   '   | |: |  | :   /    /  | """,  # noqa
    """ .   | '___'   | .; |   | |  | |\  \    `.'   | .; '  : |__.    ' / | """,  # noqa
    """ '   ; : .'|   :    |   | |  |/  `----.   |   :    |  | '.''   ;   /| """,  # noqa
    """ '   | '/  :\   \  /|   | |--'  /  /`--'  /\   \  /;  :    '   |  / | """,  # noqa
    """ |   :    /  `----' |   |/     '--'.     /  `----' |  ,   /|   :    | """,  # noqa
    """  \   \ .'          '---'        `--'---'           ---`-'  \   \  /  """,  # noqa
    """   `---`                                                     `----'   """,  # noqa
]

# endregion


class RenderChars(object):
    # ANSI escape code，参考https://en.wikipedia.org/wiki/ANSI_escape_code
    # https://blog.csdn.net/weixin_43988842/article/details/106169040
    REVERSE_FORMAT_CHAR = b'\x1b[7m'
    NO_FORMAT_CHAR = b'\x1b[0m'
    DEL_CHAR = b'\x1b[K'  # Delete and close up
    LEFT_CHAR = b'\x1b[D'  # Move cursor left 1 space
    RIGHT_CHAR = b'\x1b[C'  # Move cursor right 1 space


INNER_PRE_INPUT_STRS = [
    'from tools.TelnetHandler import _CACHE_4_AUTO_COMPLETE',  # 这一行不要删，为了自动补全用的
]

_CACHE_4_AUTO_COMPLETE = {}  # 自动补全辅助类，用于缓存补全的上下文对象

_PYTHON_KEYWORD_4_AUTO_COMPLETE = [
    'and', 'as', 'assert', 'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
    'False', 'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'None',
    'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'True', 'try', 'while', 'with', 'yield'
]

# region utils function


def _is_name_byte(_byte: bytes):
    return _byte.isalpha() or _byte.isdigit() or _byte == b'_' or _byte == b'@'


def _get_candidate_words(context_obj, prefix):
    if context_obj is not None:
        candidate_words = []
        candidate_words.extend(dir(context_obj))
    else:  # 如果当前没有obj，就从globals里选择
        candidate_words = _CACHE_4_AUTO_COMPLETE.get('__globalkeys__', []) + _PYTHON_KEYWORD_4_AUTO_COMPLETE
        candidate_words.remove('_CACHE_4_AUTO_COMPLETE')
    if prefix == '':  # 仅当前缀为空时过滤__开头的
        return [x for x in candidate_words if not x.startswith('__')]
    return [x for x in candidate_words if x.startswith(prefix)]


def _get_remote_candidate_words(context_str, prefix, context_dir: list):
    if len(context_str) == 0:
        return ['self']
    return [x for x in context_dir if x.startswith(prefix)]


def _commonprefix(str_list: List[str]):
    # 返回字符串数组的最长公共前缀，这里trick得用到了max和min
    if not str_list:
        return ''
    s_min = min(str_list)
    s_max = max(str_list)
    for i, c in enumerate(s_min):
        if c != s_max[i]:
            return s_min[:i]
    return s_min

# endregion


class TelnetHandler(object):

    USEFUL_CMDS = frozenset([DO, DONT, WILL, WONT])
    DOACK = {
        ECHO: WILL,
        SGA: WILL,
        # NEW_ENVIRON: WONT,
    }
    WILLACK = {
        ECHO: DONT,
        SGA: DO,
        LINEMODE: DONT,
    }

    def __init__(self, client):
        self.client = client

        self.DOOPTS = {}
        self.WILLOPTS = {}

        self.current_line = []  # 输入字符串
        self.render_line = []  # 输出字符串，里面由普通字符和RENDER_CHAR组成
        self.cursor_ptr = 0  # 内容上的坐标位置
        self.last_current_line = []
        self.last_cursor_ptr = 0
        self.select_ptr = 0  # 记录shift后选择的字符初始位置，它的逻辑很巧妙，当不选择的时候就赋值为cursor_ptr，否则不变

        self.edit_history = []  # 编辑的行内记录，用于Ctrl+Z回退
        self.just_edit = False  # 用来标记最后一个操作是编辑还是回退
        self.add_to_edit_history()

        self.history = []  # 编辑的行间记录，用于上下键
        self.history_ptr = -1
        self.candidate_words = []
        self.tab_last_line = None

        self.sb = 0
        self.sbdataq = b''
        self.iac_sq = b''

        # OPERATION CMD
        # 在Pycharm ssh、KiTTY等软件，对应的是b'x1b[2A'等按键，# 5 ctrl / 2 shift / 6 ctrl+shift
        # 而在putty，mobaxterm(基于putty)等软件，b'x1b[1;2A'等按键，而且无法响应shift的复合按键
        # 参考 https://superuser.com/questions/1223266/shift-arrow-keys-working-in-kitty-but-not-putty-for-nested-tmux-configuration
        # ANSI escape code，参考 https://en.wikipedia.org/wiki/ANSI_escape_code
        self.OPERATION_CMD = {
            b'\x1b[A': self.handle_up,
            b'\x1b[2A': self.handle_shift_up,
            b'\x1b[1;2A': self.handle_shift_up,
            b'\x1b[5A': self.handle_ctrl_up,
            b'\x1b[1;5A': self.handle_ctrl_up,
            b'\x1b[6A': self.handle_ctrl_shift_up,

            b'\x1b[B': self.handle_down,
            b'\x1b[2B': self.handle_shift_down,
            b'\x1b[1;2B': self.handle_shift_down,
            b'\x1b[5B': self.handle_ctrl_down,
            b'\x1b[1;5B': self.handle_ctrl_down,
            b'\x1b[6B': self.handle_ctrl_shift_down,

            b'\x1b[D': self.handle_left,
            b'\x1b[2D': self.handle_shift_left,
            b'\x1b[1;2D': self.handle_shift_left,
            b'\x1b[5D': self.handle_ctrl_left,
            b'\x1b[1;5D': self.handle_ctrl_left,
            b'\x1b[6D': self.handle_ctrl_shift_left,

            b'\x1b[C': self.handle_right,
            b'\x1b[2C': self.handle_shift_right,
            b'\x1b[1;2C': self.handle_shift_right,
            b'\x1b[5C': self.handle_ctrl_right,
            b'\x1b[1;5C': self.handle_ctrl_right,
            b'\x1b[6C': self.handle_ctrl_shift_right,

            b'\x1b[H': self.handle_home,
            b'\x1b[F': self.handle_end,
            b'\x1b[3~': self.handle_delete,             # delete按键对应的是这个，不是ascii中的DEL
            b'\x1b[5H': self.handle_ctrl_home,          # ctrl+home
            b'\x1b[5F': self.handle_ctrl_end,           # ctrl+end
            b'\x1b[1;5H': self.handle_ctrl_home,        # ctrl+home
            b'\x1b[1;5F': self.handle_ctrl_end,         # ctrl+end
            b'\x1b[2H': self.handle_shift_home,         # shift+home
            b'\x1b[2F': self.handle_shift_end,          # shift+end
            b'\x1b[6H': self.handle_ctrl_shift_home,    # ctrl+shift+home
            b'\x1b[6F': self.handle_ctrl_shift_end,     # ctrl+shift+end
        }

        # CHAR HANDLER
        self.CHAR_HANDLER = {
            ESC: self.handle_esc,
            BSP: self.handle_backspace,
            DEL: self.handle_del,
            TAB: self.handle_tab,
            SUB: self.handle_sub,
            SOH: self.handle_soh,  # ctrl+a
            TB: self.handle_tb,  # ctrl+w
            SGA: self.handle_sga,
            DEFAULT: self.handle_default_char,
        }

        # CMD HANDLER
        self.CMD_HANDLER = {
            NOP: self.handle_nop,
            WILL: self.handle_will_wont,
            WONT: self.handle_will_wont,
            DO: self.handle_do_dont,
            DONT: self.handle_do_dont,
            SE: self.handle_se,
            SB: self.handle_sb,
        }
        self.setup()

    def setup(self):
        for k in self.DOACK:
            self.send_command(self.DOACK[k], k)

        for k in self.WILLACK:
            self.send_command(self.WILLACK[k], k)

    def handle_input(self, data):
        is_complete_line = False
        if data.find(b'\r\n') >= 0:
            raw_data_lines = data.split(b'\r\n')
            if data.endswith(b'\r\n'):
                is_complete_line = True
                raw_data_lines = raw_data_lines[:-1]
        elif data.find(b'\r\x00') >= 0:
            raw_data_lines = data.split(b'\r\x00')
            if data.endswith(b'\r\00'):
                is_complete_line = True
                raw_data_lines = raw_data_lines[:-1]
        else:
            raw_data_lines = [data]
        raw_line_idx = 0
        for raw_line in raw_data_lines:
            raw_line_idx += 1
            self.process_raw_line(raw_line)
            if is_complete_line or raw_line_idx < len(raw_data_lines):
                if len(self.current_line) > 0:
                    self.history.append(self.current_line)
                    self.history_ptr = len(self.history)
                else:
                    self.current_line.append(b'\n')
                self.write_text(b'\r\n')
                current_line_content = b''.join(self.current_line)
                if current_line_content in EASTER_EGGS_TRIGGER_WORDS:
                    for easter_str in EASTER_EGGS_DISPLAY:
                        self.client.send_ps()
                        self.client.send_data(easter_str)
                        self.write_text(b'\r\n')
                    self.client.send_ps()
                else:
                    self.client.receive_data(current_line_content)
                self.current_line = []
                self.cursor_ptr = 0
                self.render_line = []
                self.last_current_line = []
                self.last_cursor_ptr = 0

                while len(self.history) > HISTORY_MAX:
                    self.history = self.history[1:]
                    self.history_ptr -= 1

    def process_raw_line(self, raw_line):
        idx = 0
        # _logger.info(f'czx process_raw_line {raw_line}')
        while idx < len(raw_line):
            ch = bytes([raw_line[idx]])
            if ch == IAC or len(self.iac_sq) > 0 or self.sb == 1:
                idx_offset = self.process_cmd(raw_line)
                idx += idx_offset
                continue
            if ch in self.CHAR_HANDLER:
                idx_offset = self.CHAR_HANDLER[ch](raw_line, idx)
                if ch != TAB:
                    self.candidate_words = []
                    self.tab_last_line = None
            else:
                self.candidate_words = []
                self.tab_last_line = None
                idx_offset = self.CHAR_HANDLER[DEFAULT](ch)
            idx += idx_offset

    def negotiation_handler(self, cmd, opt):
        if cmd in self.CMD_HANDLER:
            self.CMD_HANDLER[cmd](cmd, opt)
        else:
            _logger.error("Unhandled option: %s %s" % (ord(cmd), ord(opt)))

    def read_sb_data(self):
        buf = self.sbdataq
        self.sbdataq = ''
        return buf

    def process_cmd(self, iac_str):
        idx = 0
        while idx < len(iac_str):
            c = bytes([iac_str[idx]])
            if not self.iac_sq:
                if c == IAC:
                    self.iac_sq += c
                elif self.sb == 1:
                    self.sbdataq += c
                idx += 1
                continue
            elif len(self.iac_sq) == 1:
                if c in self.USEFUL_CMDS:
                    self.iac_sq += c
                    idx += 1
                    continue
                self.iac_sq = b''
                if c == SB:
                    self.sb = 1
                    self.sbdataq = b''
                    idx += 1
                    continue
                elif c == SE:
                    self.sb = 0
                    self.negotiation_handler(c, NOOPT)
                    idx += 1
                    break
                else:  # unknown cmd
                    _logger.error("Unknown Comand: ", ord(c))
                    idx += 1
                    break
            elif len(self.iac_sq) == 2:
                cmd = self.iac_sq[1]
                self.iac_sq = b''
                if cmd in self.USEFUL_CMDS:
                    self.negotiation_handler(cmd, c)
                    idx += 1
                    break
        return idx

    def handle_up(self):
        if self.history_ptr > 0:
            self.history_ptr -= 1
            last_cmd = copy.deepcopy(self.history[self.history_ptr])
            self.current_line = last_cmd
            self.cursor_ptr = len(self.current_line)
            self.select_ptr = self.cursor_ptr
            self.render_input()
        else:
            self.input_warning()

    def handle_ctrl_up(self):
        self.handle_up()

    def handle_shift_up(self):
        self.handle_up()

    def handle_ctrl_shift_up(self):
        self.handle_up()

    def handle_down(self):
        if self.history_ptr < len(self.history):
            self.history_ptr += 1
            if self.history_ptr >= len(self.history):
                next_cmd = []
            else:
                next_cmd = copy.deepcopy(self.history[self.history_ptr])
            self.current_line = next_cmd
            self.cursor_ptr = len(self.current_line)
            self.select_ptr = self.cursor_ptr
            self.render_input()
        else:
            self.input_warning()

    def handle_ctrl_down(self):
        self.handle_down()

    def handle_shift_down(self):
        self.handle_down()

    def handle_ctrl_shift_down(self):
        self.handle_down()

    def handle_left(self):
        if self.cursor_ptr > 0:
            if self.select_ptr != self.cursor_ptr:
                self.cursor_ptr = min(self.select_ptr, self.cursor_ptr)
                self.select_ptr = self.cursor_ptr
            else:
                self.cursor_ptr -= 1
                self.select_ptr = self.cursor_ptr
            self.render_input()
        else:
            if self.select_ptr != self.cursor_ptr:
                # 前部有选中内容，并且光标在最前面的情况，需要把选中内容取消
                self.select_ptr = self.cursor_ptr
                self.render_input()
            else:
                self.input_warning()

    def handle_right(self):
        if self.cursor_ptr < len(self.current_line):
            if self.select_ptr != self.cursor_ptr:
                self.cursor_ptr = max(self.select_ptr, self.cursor_ptr)
                self.select_ptr = self.cursor_ptr
            else:
                self.cursor_ptr += 1
                self.select_ptr = self.cursor_ptr
            self.render_input()
        else:
            if self.select_ptr != self.cursor_ptr:
                # 尾部有选中内容，并且光标在最后面的情况，需要把选中内容取消
                self.select_ptr = self.cursor_ptr
                self.render_input()
            else:
                self.input_warning()

    def handle_shift_left(self):
        if self.cursor_ptr > 0:
            self.cursor_ptr -= 1
            self.render_input()
        else:
            self.input_warning()

    def handle_shift_right(self):
        if self.cursor_ptr < len(self.current_line):
            self.cursor_ptr += 1
            self.render_input()
        else:
            self.input_warning()

    def handle_home(self):
        if self.cursor_ptr > 0:
            self.cursor_ptr = 0
            self.select_ptr = self.cursor_ptr
            self.render_input()
        else:
            if self.select_ptr != self.cursor_ptr:
                # 前部有选中内容，并且光标在最前面的情况，需要把选中内容取消
                self.select_ptr = self.cursor_ptr
                self.render_input()
            else:
                self.input_warning()

    def handle_end(self):
        if self.cursor_ptr == len(self.current_line):
            if self.select_ptr != self.cursor_ptr:
                # 尾部有选中内容，并且光标在最后面的情况，需要把选中内容取消
                self.select_ptr = self.cursor_ptr
                self.render_input()
            else:
                self.input_warning()
        else:
            self.cursor_ptr = len(self.current_line)
            self.select_ptr = self.cursor_ptr
            self.render_input()

    def handle_delete(self):
        # delete按键对应的是这个，不是ascii中的DEL
        if self.select_ptr == self.cursor_ptr:
            if self.cursor_ptr == len(self.current_line):
                self.input_warning()
                return
            del self.current_line[self.cursor_ptr]
        elif self.select_ptr > self.cursor_ptr:
            del self.current_line[self.cursor_ptr: self.select_ptr]
            self.select_ptr = self.cursor_ptr
        else:
            del self.current_line[self.select_ptr: self.cursor_ptr]
            self.cursor_ptr = self.select_ptr
        self.render_input()
        self.add_to_edit_history()

    def handle_ctrl_home(self):
        self.handle_home()

    def handle_ctrl_end(self):
        self.handle_end()

    def handle_shift_home(self):
        if self.cursor_ptr > 0:
            self.cursor_ptr = 0
            self.render_input()
        else:
            self.input_warning()

    def handle_shift_end(self):
        if self.cursor_ptr == len(self.current_line):
            self.input_warning()
        else:
            self.cursor_ptr = len(self.current_line)
            self.render_input()

    def handle_ctrl_shift_home(self):
        self.handle_shift_home()

    def handle_ctrl_shift_end(self):
        self.handle_shift_end()

    def handle_ctrl_left(self):
        # 找到当前游标往前的第一个不同类型字符的位置，如果没有那就是行首
        if self.cursor_ptr > 0:
            name_byte_flag = _is_name_byte(self.current_line[self.cursor_ptr - 1])
            target_idx = 0
            for idx in range(self.cursor_ptr - 1, 0, -1):
                if name_byte_flag ^ _is_name_byte(self.current_line[idx]):
                    # 满足有且只有一，采用亦或操作
                    target_idx = idx + 1
                    break
            self.cursor_ptr = target_idx
            self.select_ptr = self.cursor_ptr
            self.render_input()
        else:
            self.input_warning()

    def handle_ctrl_right(self):
        # 找到当前游标往后的第一个不同类型字符的位置，如果没有那就是行尾
        if self.cursor_ptr == len(self.current_line):
            self.input_warning()
        else:
            name_byte_flag = _is_name_byte(self.current_line[self.cursor_ptr])
            target_idx = len(self.current_line)
            for idx in range(self.cursor_ptr, len(self.current_line)):
                if name_byte_flag ^ _is_name_byte(self.current_line[idx]):
                    # 满足有且只有一，采用亦或操作
                    target_idx = idx
                    break
            self.cursor_ptr = target_idx
            self.select_ptr = self.cursor_ptr
            self.render_input()

    def handle_ctrl_shift_left(self):
        # 找到当前游标往前的第一个不同类型字符的位置，如果没有那就是行首
        if self.cursor_ptr > 0:
            name_byte_flag = _is_name_byte(self.current_line[self.cursor_ptr - 1])
            target_idx = 0
            for idx in range(self.cursor_ptr - 1, 0, -1):
                if name_byte_flag ^ _is_name_byte(self.current_line[idx]):
                    # 满足有且只有一，采用亦或操作
                    target_idx = idx + 1
                    break
            self.cursor_ptr = target_idx
            self.render_input()
        else:
            self.input_warning()

    def handle_ctrl_shift_right(self):
        # 找到当前游标往后的第一个不同类型字符的位置，如果没有那就是行尾
        if self.cursor_ptr == len(self.current_line):
            self.input_warning()
        else:
            name_byte_flag = _is_name_byte(self.current_line[self.cursor_ptr])
            target_idx = len(self.current_line)
            for idx in range(self.cursor_ptr, len(self.current_line)):
                if name_byte_flag ^ _is_name_byte(self.current_line[idx]):
                    # 满足有且只有一，采用亦或操作
                    target_idx = idx
                    break
            self.cursor_ptr = target_idx
            self.render_input()

    def handle_default_char(self, ch):
        self.current_line.insert(self.cursor_ptr, ch)
        self.cursor_ptr += 1
        self.select_ptr = self.cursor_ptr
        self.render_input()
        self.add_to_edit_history()
        return 1

    def add_to_edit_history(self):
        self.edit_history.append([self.cursor_ptr, list(self.current_line), self.select_ptr])
        if len(self.edit_history) > EDIT_HISTORY_MAX:
            self.edit_history = self.edit_history[len(self.edit_history) - EDIT_HISTORY_MAX:]
        self.just_edit = True

    def handle_esc(self, raw_line, idx):
        if raw_line[idx:idx + 3] in self.OPERATION_CMD:
            self.OPERATION_CMD[raw_line[idx:idx + 3]]()
            return 3
        if raw_line[idx:idx + 4] in self.OPERATION_CMD:
            self.OPERATION_CMD[raw_line[idx:idx + 4]]()
            return 4
        if raw_line[idx:idx + 5] in self.OPERATION_CMD:
            self.OPERATION_CMD[raw_line[idx:idx + 6]]()
            return 5
        if raw_line[idx:idx + 6] in self.OPERATION_CMD:
            self.OPERATION_CMD[raw_line[idx:idx + 6]]()
            return 6
        _logger.error(f'handle_esc {raw_line} not in handle')
        return 3

    def handle_backspace(self, raw_line, idx):
        if self.select_ptr == self.cursor_ptr:
            if self.cursor_ptr == 0:
                self.input_warning()
                return 1
            self.cursor_ptr -= 1
            self.select_ptr = self.cursor_ptr
            del self.current_line[self.cursor_ptr]
        elif self.select_ptr > self.cursor_ptr:
            del self.current_line[self.cursor_ptr: self.select_ptr]
            self.select_ptr = self.cursor_ptr
        else:
            del self.current_line[self.select_ptr: self.cursor_ptr]
            self.cursor_ptr = self.select_ptr
        self.render_input()
        self.add_to_edit_history()
        return 1

    def _get_input_context(self):
        # 获取当前输入的补全前缀和上下文
        current_idx = self.cursor_ptr
        for i in range(current_idx - 1, -1, -1):
            if _is_name_byte(self.current_line[i]):
                current_idx = i
            else:
                break
        if current_idx <= 0 or self.current_line[current_idx - 1] != b'.':
            return b'', b''.join(self.current_line[current_idx:self.cursor_ptr])
        square_bracket = 0  # 中括号
        parentheses = 0  # 小括号
        # 当前位置就是.了
        point_idx = current_idx - 1
        for i in range(point_idx - 1, -1, -1):
            current_char = self.current_line[i]
            if current_char == b'(':
                if parentheses == 0:
                    break
                parentheses -= 1
            elif current_char == b')':
                parentheses += 1
            elif current_char == b'[':
                if square_bracket == 0:
                    break
                square_bracket -= 1
            elif current_char == b']':
                square_bracket += 1
            elif _is_name_byte(current_char) or current_char == b'.':
                pass
            else:  # 遇到其他字符或者空格了
                if parentheses == 0 and square_bracket == 0:
                    break
            current_idx = i
        return b''.join(self.current_line[current_idx:point_idx]), b''.join(self.current_line[point_idx + 1:self.cursor_ptr])

    def _handle_tab_input(self, suffix):
        # _logger.info(f"_handle_tab_input {suffix}")
        for c in suffix:
            self.current_line.insert(self.cursor_ptr, c.encode())
            self.cursor_ptr += 1
        self.select_ptr = self.cursor_ptr
        self.render_input()
        self.add_to_edit_history()

    def handle_tab(self, raw_line, idx):
        # _logger.info(f"handle_tab once {self.current_line} {self.tab_last_line}")
        if self.current_line != self.tab_last_line:
            self.tab_last_line = list(self.current_line)
            context, prefix = self._get_input_context()
            context_str = context.decode()
            prefix_str = prefix.decode()
            if context == b'':
                context_obj = None
            else:
                self.client.console.try_runsource(f'_CACHE_4_AUTO_COMPLETE["""{context_str}"""] = {context_str}')
                context_obj = _CACHE_4_AUTO_COMPLETE.get(context_str, None)
            self.client.console.try_runsource('_CACHE_4_AUTO_COMPLETE["__globalkeys__"] = list(globals().keys())')
            self.candidate_words = _get_candidate_words(context_obj, prefix_str)

            if len(self.candidate_words) == 0:
                # _logger.info("handle_tab status 1-1")
                self.render_information("No Candidate Word For AutoCompletion")
                self.input_warning()
            elif len(self.candidate_words) == 1:
                if self.candidate_words[0] == prefix_str:
                    # 当前单次已经被填充完整，那么就再尝试添加一个一个后缀，获取当前上下文（包含prefix）对象，依据其类型增加.或者(
                    # _logger.info("handle_tab status 1-2")

                    if context_str == '':
                        full_context_str = f'{prefix_str}'
                    else:
                        full_context_str = f'{context_str}.{prefix_str}'

                    callableResult: bool
                    self.client.console.try_runsource(
                        f'_CACHE_4_AUTO_COMPLETE["""{full_context_str}"""] = {full_context_str}')
                    full_context_obj = _CACHE_4_AUTO_COMPLETE.get(full_context_str, None)
                    callableResult = callable(full_context_obj)
                    if callableResult:
                        self._handle_tab_input('(')
                    else:
                        self._handle_tab_input('.')
                else:
                    # _logger.info("handle_tab status 1-3")
                    self._handle_tab_input(self.candidate_words[0].replace(prefix_str, ''))
            else:
                # 找最长前缀相同子串
                longest_prefix = _commonprefix(self.candidate_words)
                if longest_prefix == prefix_str:
                    # _logger.info("handle_tab status 1-4")
                    self.render_candidate_words(self.candidate_words)
                else:
                    # _logger.info("handle_tab status 1-5")
                    self._handle_tab_input(longest_prefix.replace(prefix_str, '', 1))
        else:  # 优化，当输入内容相同，不再尝试获取运行时对象，而是用缓存的self.candidate_words
            if len(self.candidate_words) > 1:
                # _logger.info("handle_tab status 1-6")
                self.render_candidate_words(self.candidate_words)
            elif len(self.candidate_words) == 1:  # 之前肯定被填充完成了，所以不需要做什么
                # _logger.info("handle_tab status 1-7")
                raise NotImplementedError("this suppose not to be happened")
            else:
                # _logger.info("handle_tab status 1-8")
                self.render_information("No Candidate Word For AutoCompletion")
                self.input_warning()
        # _logger.info(f"handle_tab {self.candidate_words}")
        return 1

    def render_information(self, message):
        # 额外需要打印的信息，会在打印后再输出当前行
        self.write_text(b'\r\n')
        self.write_text(f'--- Info: {message}'.encode())
        self.write_text(b'\r\n')
        self.client.send_ps()
        # 模拟上一行为空的情况，这样可以重新打印出当前的行
        self.last_current_line = []
        self.last_cursor_ptr = 0
        self.render_line = []
        self.render_input()

    def render_candidate_words(self, candidate_words):
        # 渲染自动补全的候选词
        self.write_text(b'\r\n')
        #  最多展示20个，每行5个
        candidate_words_len = len(candidate_words)
        exceed = candidate_words_len > AUTOCOMPLETE_DISPLAY_MAX
        candidate_words = candidate_words[:AUTOCOMPLETE_DISPLAY_MAX]
        lines = min(math.ceil(len(candidate_words) / AUTOCOMPLETE_WORLDS_INLINE), AUTOCOMPLETE_MAX_LINES)
        word_max = max([len(x) for x in candidate_words])
        word_width = word_max + AUTOCOMPLETE_WORD_SPACING
        for i in range(lines):
            self.write_text(b' ' * AUTOCOMPLETE_WORD_SPACING)
            for j in range(AUTOCOMPLETE_WORLDS_INLINE):
                cur_idx = i * AUTOCOMPLETE_WORLDS_INLINE + j
                if cur_idx >= len(candidate_words):
                    break
                self.write_text(candidate_words[cur_idx].encode())
                self.write_text(b' ' * (word_width - len(candidate_words[cur_idx])))
            self.write_text(b'\r\n')
        if exceed:
            self.write_text(f'--- [{candidate_words_len}] Candidate Words, '
                            f'Only [{AUTOCOMPLETE_DISPLAY_MAX}] Display Here ---\r\n'.encode())
        self.client.send_ps()
        # 模拟上一行为空的情况，这样可以重新打印出当前的行
        self.last_current_line = []
        self.last_cursor_ptr = 0
        self.render_line = []
        self.render_input()

    def handle_sub(self, raw_line, idx):
        # Ctrl+Z撤销逻辑
        if self.just_edit:
            self.edit_history = self.edit_history[:-1]
            self.just_edit = False
        if self.edit_history:
            self.cursor_ptr, self.current_line, self.select_ptr = self.edit_history[-1]
            self.edit_history = self.edit_history[:-1]
            self.render_input()
        else:
            self.input_warning()
        return 1

    def handle_ctrl_a(self):
        if not self.current_line:
            self.input_warning()
        else:
            self.cursor_ptr = len(self.current_line)
            self.select_ptr = 0
            self.render_input()

    def handle_ctrl_w(self):
        # 如果有选中内容，删除选中内容，否则删除往前的当前字符类型(name/not_name)的最长字符
        if self.cursor_ptr > 0:
            if self.select_ptr == self.cursor_ptr:
                # 找到当前游标往前的第一个不同类型字符的位置，如果没有那就是行首
                name_byte_flag = _is_name_byte(self.current_line[self.cursor_ptr - 1])
                target_idx = 0
                for idx in range(self.cursor_ptr - 1, 0, -1):
                    if name_byte_flag ^ _is_name_byte(self.current_line[idx]):
                        # 满足有且只有一，采用亦或操作
                        target_idx = idx + 1
                        break
                self.cursor_ptr = target_idx
                del self.current_line[self.cursor_ptr: self.select_ptr]
                self.select_ptr = self.cursor_ptr
            elif self.select_ptr > self.cursor_ptr:
                del self.current_line[self.cursor_ptr: self.select_ptr]
                self.select_ptr = self.cursor_ptr
            else:
                del self.current_line[self.select_ptr: self.cursor_ptr]
                self.cursor_ptr = self.select_ptr
        else:
            if self.select_ptr != self.cursor_ptr:
                del self.current_line[self.cursor_ptr: self.select_ptr]
                self.select_ptr = self.cursor_ptr
            else:
                self.input_warning()
                return
        self.render_input()
        self.add_to_edit_history()

    def handle_soh(self, raw_line, idx):
        # Ctrl+A的逻辑
        self.handle_ctrl_a()
        return 1

    def handle_tb(self, raw_line, dix):
        # Ctrl+W逻辑
        self.handle_ctrl_w()
        return 1

    def handle_sga(self, raw_line, idx):
        # _logger.info(f"handle_sga {idx}")
        return 1

    def handle_del(self, raw_line, idx):
        return self.handle_backspace(raw_line, idx)

    def handle_nop(self, cmd, opt):
        self.send_command(NOP)

    def handle_will_wont(self, cmd, opt):
        if opt in self.WILLACK:
            self.send_command(self.WILLACK[opt], opt)
        else:
            self.send_command(DONT, opt)
        if cmd == WILL and opt == TTYPE:
            self.write_cooked(IAC + SB + TTYPE + SEND + IAC + SE)

    def handle_do_dont(self, cmd, opt):
        if opt in self.DOACK:
            self.send_command(self.DOACK[opt], opt)
        else:
            self.send_command(WONT, opt)

    def handle_se(self, cmd, opt):
        subreq = self.read_sb_data()
        if subreq[0] == TTYPE and subreq[1] == IS:
            pass

    def handle_sb(self, cmd, opt):
        pass

    def send_command(self, cmd, opt=None):
        if cmd in [DO, DONT]:
            if opt not in self.DOOPTS:
                self.DOOPTS[opt] = None
            if (cmd == DO and self.DOOPTS[opt] is not True) or (cmd == DONT and self.DOOPTS[opt] is not False):
                self.DOOPTS[opt] = (cmd == DO)
                self.write_cooked(IAC + cmd + opt)
        elif cmd in [WILL, WONT]:
            if opt not in self.WILLOPTS:
                self.WILLOPTS[opt] = None
            if (cmd == WILL and self.WILLOPTS[opt] is not True) or (cmd == WONT and self.WILLOPTS is not False):
                self.WILLOPTS[opt] = (cmd == WILL)
                self.write_cooked(IAC + cmd + opt)
        else:
            self.write_cooked(IAC + cmd)

    def render_input(self):
        # 由self.current_line渲染到self.render_line
        # 先存储部分数据
        last_render_line = list(self.render_line)
        self.render_line = list(self.current_line)
        # 先渲染新行
        if self.select_ptr == self.cursor_ptr:
            render_cursor_ptr = self.cursor_ptr
            self.render_line.extend([RenderChars.LEFT_CHAR] * (len(self.render_line) - render_cursor_ptr))
        elif self.select_ptr > self.cursor_ptr:  # 选择内容在光标的右侧
            render_cursor_ptr = self.cursor_ptr + 2
            self.render_line.insert(self.cursor_ptr, RenderChars.REVERSE_FORMAT_CHAR)
            self.render_line.insert(self.select_ptr + 1, RenderChars.NO_FORMAT_CHAR)
            self.render_line.extend([RenderChars.LEFT_CHAR] * (len(self.render_line) - render_cursor_ptr))
        else:  # 选择内容在光标的左侧
            render_cursor_ptr = self.cursor_ptr + 2
            self.render_line.insert(self.select_ptr, RenderChars.REVERSE_FORMAT_CHAR)
            self.render_line.insert(self.cursor_ptr + 1, RenderChars.NO_FORMAT_CHAR)
            self.render_line.extend([RenderChars.LEFT_CHAR] * (len(self.render_line) - render_cursor_ptr))
        # 对比新行和旧行数据，只重新渲染需要更改的部分
        same_idx = -1
        for i in range(min(len(self.render_line), len(last_render_line))):
            if self.render_line[i] != last_render_line[i]:
                break
            if self.render_line[i] == RenderChars.REVERSE_FORMAT_CHAR:
                break
            if last_render_line[i] == RenderChars.REVERSE_FORMAT_CHAR:
                break
            else:
                same_idx = i
        diff_idx = same_idx + 1
        # _logger.info(f"diff_idx {diff_idx}")

        if diff_idx >= len(last_render_line):  # 新的行渲染的内容多，继续渲染就可以
            # _logger.info(f"status 1")
            self.write_text(b''.join(self.render_line[diff_idx:]))
        elif diff_idx >= len(self.render_line):  # 新的行渲染的内容少，需要区分是右移还是左删
            if last_render_line[diff_idx] == RenderChars.LEFT_CHAR:  # 右移
                # _logger.info(f"status 2")
                self.write_text(RenderChars.RIGHT_CHAR * (len(last_render_line) - diff_idx))
            else:  # 最右侧往左删
                valid_diff_idx = [_x for _x in last_render_line[diff_idx:] if _x not in
                                  [RenderChars.REVERSE_FORMAT_CHAR, RenderChars.NO_FORMAT_CHAR, RenderChars.LEFT_CHAR]]
                left_char_list = [_x for _x in last_render_line[diff_idx:] if _x == RenderChars.LEFT_CHAR]
                # _logger.info(f"status 3 move right{len(left_char_list)}")
                self.write_text(RenderChars.RIGHT_CHAR * len(left_char_list))
                # _logger.info(f"status 3 clear left{len(valid_diff_idx)}")
                self.write_text((RenderChars.LEFT_CHAR + RenderChars.DEL_CHAR) * len(valid_diff_idx))
        else:  # 不一样的字符或者遇到了format
            valid_diff_idx = [_x for _x in last_render_line[diff_idx:] if _x not in
                              [RenderChars.REVERSE_FORMAT_CHAR, RenderChars.NO_FORMAT_CHAR, RenderChars.LEFT_CHAR]]
            # _logger.info(f"status 4 {len(valid_diff_idx)}")
            # 从之前cursor_ptr的位置移动到最末端
            self.write_text(RenderChars.RIGHT_CHAR * (len(self.last_current_line) - self.last_cursor_ptr))
            # 然后删掉diff_idx到末尾的老字符串
            self.write_text((RenderChars.LEFT_CHAR + RenderChars.DEL_CHAR) * len(valid_diff_idx))
            self.write_text(b''.join(self.render_line[diff_idx:]))

        self.last_current_line = list(self.current_line)
        self.last_cursor_ptr = self.cursor_ptr
        # _logger.info(f"current_line {self.current_line} {self.cursor_ptr} {self.select_ptr}")
        # _logger.info(f"render_input {self.render_line}")

    def input_warning(self):
        self.write_text(BELL)

    def write_text(self, text):
        if text == b'':
            return
        text = text.replace(IAC, IAC + IAC)
        text = text.replace(b'\n', b'\r\n')
        self.write_cooked(text)

    def write_cooked(self, text):
        self.client.send_bytes(text)


class TelnetConnection(object):

    def __init__(self, conn):
        self.conn = conn
        self.console = Console(self)
        for pre_input_str in INNER_PRE_INPUT_STRS:
            self.console.try_runsource(pre_input_str)

        self.handler = TelnetHandler(self)
        self.console.interact()
        self.ps_flag = sys.ps1  # 当前的前缀标识符

    def raw_input(self, data):
        self.handler.handle_input(data)

    def receive_data(self, data):
        try:
            message = data.decode()
        except Exception:
            self.send_data("decode error")
            return
        self.runscript(message)

    def runscript(self, script):
        if script in QUIT_FLAGS:
            self.close()
            return
        buff = StringIO()
        temp = sys.stdout
        sys.stdout = buff

        more = self.console.push(script)
        sys.stdout = temp
        self.console.write(buff.getvalue())

        if more:
            self.ps_flag = sys.ps2
            self.send_data(sys.ps2)
        else:
            self.ps_flag = sys.ps1
            self.send_data(sys.ps1)

    def send_ps(self):
        self.send_data(self.ps_flag)

    def send_data(self, data):
        self.send(bytes(data, "utf-8"))

    def send_bytes(self, data):
        self.send(data)

    def send(self, data):
        raise NotImplementedError("TelnetConnection send Not Implement")

    def close(self):
        if self.conn:
            _logger.info("Telnet client closed.")
            self.conn.close()
            self.conn = None


class Console(InteractiveConsole):
    def __init__(self, client, locals=None, filename="<console>"):
        InteractiveConsole.__init__(self, locals, filename)
        self.client = client

    def interact(self, banner=None):
        try:
            sys.ps1
        except AttributeError:
            sys.ps1 = ">>> "
        try:
            sys.ps2
        except AttributeError:
            sys.ps2 = "... "
        cprt = 'Type "help", "copyright", "credits" or "license" for more information.'
        if banner is None:
            self.write("Python %s on %s\r\n%s\r\n(%s)\r\n>>> " %
                       (sys.version, sys.platform, cprt,
                        self.__class__.__name__))
        else:
            self.write("%s\n" % str(banner))

    def try_runsource(self, source: str):
        try:
            code = self.compile(source, self.filename, "single")
        except (OverflowError, SyntaxError, ValueError) as err:
            _logger.info(f'try_runsource status 1 {err}')
            return None
        if code is None:
            _logger.info('try_runsource status 2')
            return None
        try:
            ret = self.runcode(code)
        except NameError as err:
            _logger.info(f'try_runsource status 3 NameError {err}')
            return None
        return ret

    def write(self, data):
        data = data.replace('\r\n', '\n').replace('\n', '\r\n')
        self.client.send_data(data)

    def showtraceback(self):
        """Display the exception that just occurred.

        We remove the first stack item because it is our own code.

        The output is written by self.write(), below.

        """
        import traceback
        trace_str = traceback.format_exc()
        self.write(trace_str)


class GeventTelnetServer:

    class GeventConn(TelnetConnection):

        def send(self, data):
            self.conn.send(data)

    def __init__(self, ip: str, port: int):
        self._ip = ip
        self._port = port
        self._server = None

    def start_server(self):
        import gevent
        from gevent.server import StreamServer
        from gevent.pool import Pool
        self.pool = Pool(30)
        self._server = StreamServer((self._ip, self._port), self.handle_request, spawn=self.pool)
        telnet_task = gevent.spawn(self._server.serve_forever)
        _logger.info("GeventTelnetServer start at: %s", (self._ip, self._port))
        return telnet_task

    def handle_request(self, conn, addr):
        _logger.info("Telnet connection from: %s", addr)
        client = GeventTelnetServer.GeventConn(conn)
        # 在这里可以做一下预加载的指令
        for input_str in PRE_INPUT_STRS:
            client.raw_input(str.encode(f'{input_str}\r\n'))
        while True:
            try:
                data = conn.recv(1024)
            except Exception as err:
                _logger.info(f"Telnet connection Status 2: {err}")
                break
            if not data:
                _logger.info("Telnet connection Status 3")
                break
            client.raw_input(data)
        client.close()

    def stop(self):
        self._server.close()
        self._server.stop()


def run_telnet_server():
    telnetServer = GeventTelnetServer(config.TELNET_IP, config.TELNET_PORT)
    telnet_task = telnetServer.start_server()
    _logger.info(f"console listen at {config.TELNET_IP}: {config.TELNET_PORT}")
    return telnet_task
