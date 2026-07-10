import { WorkflowNodeExecutor } from '../../types';

const BoolGateExecutor: WorkflowNodeExecutor = {
  async run(input: any, config: any) {
    const raw = input?.valueIn !== undefined ? input.valueIn : (config?.value ?? false);
    const boolVal = raw === true || raw === 'true' || raw === 1;
    if (!boolVal) {
      throw new Error('BoolGate: 输入值为 False，流程中断');
    }
    return { value: true };
  },
};

export default BoolGateExecutor;
