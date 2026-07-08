import { WorkflowNodeExecutor } from '../../types';

const NumberExecutor: WorkflowNodeExecutor = {
  async run(input: any, config: any) {
    const rawValue = input?.valueIn !== undefined ? input.valueIn : config.value;
    const numValue = parseFloat(String(rawValue ?? 0));
    return { value: isNaN(numValue) ? 0 : numValue };
  },
};

export default NumberExecutor;
