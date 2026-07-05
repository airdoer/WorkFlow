import { WorkflowNodeExecutor } from '../../types';

const JsonExecutor: WorkflowNodeExecutor = {
  async run(input: any, config: any) {
    const { FlowApi } = await import('../../services/FlowApi');
    return FlowApi.runNode('json', config, input);
  },
};

export default JsonExecutor;
