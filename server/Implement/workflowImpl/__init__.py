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
from Implement.workflowImpl.c7ServerExecutor import C7ServerExecutor
from Implement.workflowImpl.kdipExecutor import KdipExecutor
from Implement.workflowImpl.kimNotifyExecutor import KimNotifyExecutor
from Implement.workflowImpl.boolGateExecutor import BoolGateExecutor
from Implement.workflowImpl.tableExecutor import TableExecutor

ExecutorManager.register(ExcelExecutor())
ExecutorManager.register(JsonExecutor())
ExecutorManager.register(LuaExecutor())
ExecutorManager.register(PromptExecutor())
ExecutorManager.register(P4FileExecutor())
ExecutorManager.register(StringExecutor())
ExecutorManager.register(BoolExecutor())
ExecutorManager.register(NumberExecutor())
ExecutorManager.register(DiffExecutor())
ExecutorManager.register(C7ServerExecutor())
ExecutorManager.register(KdipExecutor())
ExecutorManager.register(KimNotifyExecutor())
ExecutorManager.register(BoolGateExecutor())
ExecutorManager.register(TableExecutor())
