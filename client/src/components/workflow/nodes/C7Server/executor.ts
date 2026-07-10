import { WorkflowNodeExecutor } from '../../types';

const C7ServerExecutor: WorkflowNodeExecutor = {
  async run(_input: any, config: any) {
    const serverName = config?.serverName;
    if (!serverName) throw new Error('serverName 不能为空');
    return { serverName: String(serverName) };
  },
};

export default C7ServerExecutor;
