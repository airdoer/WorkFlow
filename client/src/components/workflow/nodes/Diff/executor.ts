import { WorkflowNodeExecutor } from '../../types';

/**
 * Front-end Diff executor (client-side stub only).
 * Real execution runs on the backend (server/Implement/workflowImpl/diffExecutor.py).
 */
const DiffExecutor: WorkflowNodeExecutor = {
  async run(input: any, config: any) {
    const contentA = String(input?.contentA ?? config?.contentA ?? '');
    const contentB = String(input?.contentB ?? config?.contentB ?? '');
    const isSame = contentA === contentB;

    const stats = {
      additions: 0,
      deletions: 0,
      changedLines: 0,
      lengthA: contentA.length,
      lengthB: contentB.length,
    };

    return { isSame, contentA, contentB, unifiedDiff: '', stats };
  },
};

export default DiffExecutor;
