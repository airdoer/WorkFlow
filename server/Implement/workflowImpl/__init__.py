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
from Implement.workflowImpl.gateExecutor import GateExecutor
from Implement.workflowImpl.tableExecutor import TableExecutor
from Implement.workflowImpl.excelSearchExecutor import ExcelSearchExecutor

# New: Collection executors
from Implement.workflowImpl.mapExecutor import MapExecutor
from Implement.workflowImpl.filterExecutor import FilterExecutor
from Implement.workflowImpl.reduceExecutor import ReduceExecutor
from Implement.workflowImpl.sortExecutor import SortExecutor
from Implement.workflowImpl.joinExecutor import JoinExecutor
from Implement.workflowImpl.lookupExecutor import LookupExecutor
from Implement.workflowImpl.splitExecutor import SplitExecutor
from Implement.workflowImpl.distinctExecutor import DistinctExecutor
from Implement.workflowImpl.flattenExecutor import FlattenExecutor
from Implement.workflowImpl.groupbyExecutor import GroupByExecutor

# New: Builder executors
from Implement.workflowImpl.listBuilderExecutor import ListBuilderExecutor
from Implement.workflowImpl.objectBuilderExecutor import ObjectBuilderExecutor
from Implement.workflowImpl.dictBuilderExecutor import DictBuilderExecutor

# New: Expression executors
from Implement.workflowImpl.calculateExecutor import CalculateExecutor
from Implement.workflowImpl.templateExecutor import TemplateExecutor
from Implement.workflowImpl.conditionExecutor import ConditionExecutor
from Implement.workflowImpl.formatExecutor import FormatExecutor

# New: AI executors
from Implement.workflowImpl.llmExecutor import LLMExecutor

# New: Control Flow executors
from Implement.workflowImpl.ifExecutor import IfExecutor
from Implement.workflowImpl.loopExecutor import LoopExecutor
from Implement.workflowImpl.switchExecutor import SwitchExecutor

# New: Data Source executors
from Implement.workflowImpl.httpExecutor import HTTPExecutor
from Implement.workflowImpl.redisExecutor import RedisExecutor
from Implement.workflowImpl.fileExecutor import FileExecutor
from Implement.workflowImpl.serverCommandExecutor import ServerCommandExecutor
from Implement.workflowImpl.sealExecutor import SealExecutor
from Implement.workflowImpl.jenkinsDeployExecutor import JenkinsDeployExecutor

# --- Register all executors ---

# Original executors
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
ExecutorManager.register(GateExecutor())
ExecutorManager.register(TableExecutor())
ExecutorManager.register(ExcelSearchExecutor())

# Collection executors
ExecutorManager.register(MapExecutor())
ExecutorManager.register(FilterExecutor())
ExecutorManager.register(ReduceExecutor())
ExecutorManager.register(SortExecutor())
ExecutorManager.register(JoinExecutor())
ExecutorManager.register(LookupExecutor())
ExecutorManager.register(SplitExecutor())
ExecutorManager.register(DistinctExecutor())
ExecutorManager.register(FlattenExecutor())
ExecutorManager.register(GroupByExecutor())

# Builder executors
ExecutorManager.register(ListBuilderExecutor())
ExecutorManager.register(ObjectBuilderExecutor())
ExecutorManager.register(DictBuilderExecutor())

# Expression executors
ExecutorManager.register(CalculateExecutor())
ExecutorManager.register(TemplateExecutor())
ExecutorManager.register(ConditionExecutor())
ExecutorManager.register(FormatExecutor())

# AI executors
ExecutorManager.register(LLMExecutor())

# Control Flow executors
ExecutorManager.register(IfExecutor())
ExecutorManager.register(LoopExecutor())
ExecutorManager.register(SwitchExecutor())

# Data Source executors
ExecutorManager.register(HTTPExecutor())
ExecutorManager.register(RedisExecutor())
ExecutorManager.register(FileExecutor())
ExecutorManager.register(ServerCommandExecutor())
ExecutorManager.register(SealExecutor())
ExecutorManager.register(JenkinsDeployExecutor())
