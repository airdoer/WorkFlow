from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor, ExecutorManager
from Implement.workflowImpl.excelExecutor import ExcelExecutor
from Implement.workflowImpl.jsonExecutor import JsonExecutor
from Implement.workflowImpl.luaExecutor import LuaExecutor
from Implement.workflowImpl.promptExecutor import PromptExecutor
from Implement.workflowImpl.p4FileExecutor import P4FileExecutor

ExecutorManager.register(ExcelExecutor())
ExecutorManager.register(JsonExecutor())
ExecutorManager.register(LuaExecutor())
ExecutorManager.register(PromptExecutor())
ExecutorManager.register(P4FileExecutor())
