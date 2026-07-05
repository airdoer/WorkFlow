import { WorkflowNodeExecutor } from '../../types';

const ExcelExecutor: WorkflowNodeExecutor = {
  async run(input: any, config: any) {
    const { FlowApi } = await import('../../services/FlowApi');
    return FlowApi.runNode('excel', config, input);
  },
};

export default ExcelExecutor;
