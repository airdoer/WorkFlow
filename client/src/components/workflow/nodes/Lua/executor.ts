import { WorkflowNodeExecutor } from '../../types';

const LuaExecutor: WorkflowNodeExecutor = {
  async run(input: any, config: any) {
    const { FlowApi } = await import('../../services/FlowApi');
    return FlowApi.runNode('lua', config, input);
  },
};

export default LuaExecutor;
