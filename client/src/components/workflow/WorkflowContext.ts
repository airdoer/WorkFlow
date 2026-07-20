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
  /**
   * Compact mode: true = hide execution result details on nodes (only show input params).
   * false = show full output details. Defaults to false.
   */
  compactMode: boolean;
  /** Toggle compact mode on/off */
  setCompactMode: (v: boolean | ((prev: boolean) => boolean)) => void;
  /** ID of the currently selected node (synced with URL `node` param) */
  selectedNodeId: string | null;
  /** Set selected node (also syncs to URL) */
  setSelectedNodeId: (id: string | null) => void;
  /** ID of the node whose detail modal is open (synced with URL `detail` param) */
  detailNodeId: string | null;
  /** Open/close detail modal for a node (also syncs to URL) */
  setDetailNodeId: (id: string | null) => void;
  /** Read a node's run status from the external run-output store */
  getRunStatus: (nodeId: string) => string;
  /** Read a node's run output from the external run-output store */
  getRunOutput: (nodeId: string) => any;
  /** Reset a single node: clear fields, run status, output, and cache */
  resetNode: (nodeId: string) => void;
}

export const WorkflowContext = createContext<WorkflowContextValue>({
  workflowId: undefined,
  workflowName: '',
  onNodeUpdate: () => {},
  ensureSaved: async () => undefined,
  multiSelectedIds: new Set(),
  compactMode: false,
  setCompactMode: () => {},
  selectedNodeId: null,
  setSelectedNodeId: () => {},
  detailNodeId: null,
  setDetailNodeId: () => {},
  getRunStatus: () => 'idle',
  getRunOutput: () => undefined,
  resetNode: () => {},
});

export function useWorkflowContext() {
  return useContext(WorkflowContext);
}
