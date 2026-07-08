import { WorkflowNodeExecutor } from '../../types';

const StringExecutor: WorkflowNodeExecutor = {
  async run(input: any, config: any) {
    const rawValue = input?.valueIn !== undefined ? input.valueIn : config.value;
    return { value: String(rawValue ?? '') };
  },
};

export default StringExecutor;
