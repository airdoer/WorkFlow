export interface WorkflowJSON {
  nodes: Array<{
    id: string;
    type: string;
    meta: { position: { x: number; y: number } };
    data: Record<string, unknown>;
    blocks: WorkflowJSON[];
    edges: Array<{
      sourceNodeID: string;
      targetNodeID: string;
      sourcePortID?: string;
      targetPortID?: string;
    }>;
  }>;
  edges: Array<{
    sourceNodeID: string;
    targetNodeID: string;
    sourcePortID?: string;
    targetPortID?: string;
  }>;
}
