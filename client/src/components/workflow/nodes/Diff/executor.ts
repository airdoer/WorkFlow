import { WorkflowNodeExecutor } from '../../types';

const DiffExecutor: WorkflowNodeExecutor = {
  async run(input: any, config: any) {
    const stringA = input?.stringA ?? config?.stringA ?? '';
    const stringB = input?.stringB ?? config?.stringB ?? '';
    const isSame = stringA === stringB;
    return {
      diffResult: JSON.stringify({ stringA, stringB, isSame }),
      isSame,
    };
  },
};

export default DiffExecutor;
