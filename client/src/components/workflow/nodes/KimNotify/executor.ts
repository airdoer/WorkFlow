import { WorkflowNodeExecutor } from '../../types';

const KimNotifyExecutor: WorkflowNodeExecutor = {
  async run(input: any, config: any) {
    const message = input?.message || config?.message;
    const username = input?.username || config?.username;
    const groupId = input?.groupId || config?.groupId;
    if (!message) throw new Error('message 消息内容不能为空');
    if (!username && !groupId) throw new Error('username 和 groupId 至少填写一个');
    return { success: false, message: '请通过后端执行' };
  },
};

export default KimNotifyExecutor;
