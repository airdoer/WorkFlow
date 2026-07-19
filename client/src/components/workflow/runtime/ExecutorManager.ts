import type { WorkflowNodeExecutor } from '../types';

const executorMap: Record<string, WorkflowNodeExecutor> = {};

export const ExecutorManager = {
  register(type: string, executor: WorkflowNodeExecutor) {
    executorMap[type] = executor;
  },

  get(type: string): WorkflowNodeExecutor | undefined {
    return executorMap[type];
  },

  async runNode(type: string, input: any, config: any): Promise<any> {
    const executor = executorMap[type];
    if (!executor) throw new Error(`Unknown node type: ${type}`);
    return executor.run(input, config);
  },
};

import P4FileExecutor from '../nodes/P4File/executor';
import ExcelExecutor from '../nodes/Excel/executor';
import LuaExecutor from '../nodes/Lua/executor';
import JsonExecutor from '../nodes/Json/executor';
import PromptExecutor from '../nodes/Prompt/executor';
import BoolExecutor from '../nodes/Bool/executor';
import GateExecutor from '../nodes/Gate/executor';
import StringExecutor from '../nodes/String/executor';
import NumberExecutor from '../nodes/Number/executor';

ExecutorManager.register('p4file', P4FileExecutor);
ExecutorManager.register('excel', ExcelExecutor);
ExecutorManager.register('lua', LuaExecutor);
ExecutorManager.register('json', JsonExecutor);
ExecutorManager.register('prompt', PromptExecutor);
ExecutorManager.register('bool', BoolExecutor);
ExecutorManager.register('gate', GateExecutor);
ExecutorManager.register('string', StringExecutor);
ExecutorManager.register('number', NumberExecutor);
