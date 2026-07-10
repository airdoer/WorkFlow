import { WorkflowNodeExecutor } from '../../types';

const KdipExecutor: WorkflowNodeExecutor = {
  async run(input: any, config: any) {
    const serverName = input?.serverName || config?.serverName;
    const username = input?.username || config?.username;
    const cmdKey = config?.cmdKey;
    if (!serverName) throw new Error('serverName 不能为空');
    if (!cmdKey) throw new Error('cmdKey（任务名）不能为空');
    if (!username) throw new Error('username 不能为空');
    // 前端不直接调用 KDIP，由后端 executor 执行
    return { success: false, result: '请通过后端执行' };
  },
};

export default KdipExecutor;
