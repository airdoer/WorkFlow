from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor, ExecutorManager
from Implement.workflowImpl.excelExecutor import ExcelExecutor
from Implement.workflowImpl.jsonExecutor import JsonExecutor
from Implement.workflowImpl.luaExecutor import LuaExecutor
from Implement.workflowImpl.promptExecutor import PromptExecutor
from Implement.workflowImpl.p4FileExecutor import P4FileExecutor
from Implement.workflowImpl.stringExecutor import StringExecutor
from Implement.workflowImpl.boolExecutor import BoolExecutor
from Implement.workflowImpl.numberExecutor import NumberExecutor
from Implement.workflowImpl.diffExecutor import DiffExecutor

ExecutorManager.register(ExcelExecutor())
ExecutorManager.register(JsonExecutor())
ExecutorManager.register(LuaExecutor())
ExecutorManager.register(PromptExecutor())
ExecutorManager.register(P4FileExecutor())
ExecutorManager.register(StringExecutor())
ExecutorManager.register(BoolExecutor())
ExecutorManager.register(NumberExecutor())
ExecutorManager.register(DiffExecutor())
