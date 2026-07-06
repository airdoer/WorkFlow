import type { Node, Edge } from 'reactflow';

export interface WorkflowJSON {
  nodes: Node[];
  edges: Edge[];
  viewport?: { x: number; y: number; zoom: number };
}

export interface WorkflowNodeExecutor {
  run(input: any, config: any): Promise<any>;
}
