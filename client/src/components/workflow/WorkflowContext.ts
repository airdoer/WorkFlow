import { createContext, useContext } from 'react';

export interface WorkflowContextValue {
  workflowId: string | undefined;
  /**
   * Called by individual nodes when they receive a status update from the backend.
   * Shared between full-graph run (Toolbar) and single-node run (BaseNode ▶ button).
   */
  onNodeUpdate: (nodeId: string, status: string, output: any) => void;
}

export const WorkflowContext = createContext<WorkflowContextValue>({
  workflowId: undefined,
  onNodeUpdate: () => {},
});

export function useWorkflowContext() {
  return useContext(WorkflowContext);
}
