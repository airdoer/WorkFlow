import { createContext, useContext } from 'react';

export interface WorkflowContextValue {
  workflowId: string | undefined;
  workflowName: string;
  /**
   * Called by individual nodes when they receive a status update from the backend.
   * Shared between full-graph run (Toolbar) and single-node ▶ button.
   */
  onNodeUpdate: (nodeId: string, status: string, output: any) => void;
  /**
   * Ensure the workflow is saved before running.
   * Returns the saved workflowId (or existing one if already saved).
   * Shows a warning message if the workflow is new (no ID).
   */
  ensureSaved: () => Promise<string | undefined>;
  /**
   * Set of node IDs that are currently multi-selected (Ctrl+click).
   * Empty when 0 or 1 node is selected.
   */
  multiSelectedIds: Set<string>;
}

export const WorkflowContext = createContext<WorkflowContextValue>({
  workflowId: undefined,
  workflowName: '',
  onNodeUpdate: () => {},
  ensureSaved: async () => undefined,
  multiSelectedIds: new Set(),
});

export function useWorkflowContext() {
  return useContext(WorkflowContext);
}
