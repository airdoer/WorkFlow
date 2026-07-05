import { WorkflowNodeExecutor } from '../../types';

const PromptExecutor: WorkflowNodeExecutor = {
  async run(input: any, config: any) {
    const { FlowApi } = await import('../../services/FlowApi');
    return FlowApi.runNode('prompt', config, input);
  },
};

export default PromptExecutor;
