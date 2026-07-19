import { WorkflowNodeExecutor } from '../../types';

const GateExecutor: WorkflowNodeExecutor = {
  async run(input: any, config: any) {
    const enabledRaw = input?.enabledIn !== undefined ? input.enabledIn : (config?.enabled ?? false);
    const enabled = enabledRaw === true || enabledRaw === 'true' || enabledRaw === 1;

    if (!enabled) {
      throw new Error('Gate: 门控关闭');
    }

    // Gate open — pass through the value
    const value = input?.valueIn !== undefined ? input.valueIn : config?.value;
    return { value };
  },
};

export default GateExecutor;
