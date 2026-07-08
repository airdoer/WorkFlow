import { WorkflowNodeExecutor } from '../../types';

const BoolExecutor: WorkflowNodeExecutor = {
  async run(input: any, config: any) {
    // 如果有连线输入，优先使用连线值
    const rawValue = input?.valueIn !== undefined ? input.valueIn : config.value;
    const boolValue = rawValue === true || rawValue === 'true' || rawValue === 1;
    return { value: boolValue };
  },
};

export default BoolExecutor;
