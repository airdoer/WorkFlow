import { WorkflowNodeExecutor } from '../../types';

const P4FileExecutor: WorkflowNodeExecutor = {
  async run(input: any, config: any) {
    const { FlowApi } = await import('../../services/FlowApi');
    return FlowApi.runNode('p4file', config, input);
  },
};

export default P4FileExecutor;
