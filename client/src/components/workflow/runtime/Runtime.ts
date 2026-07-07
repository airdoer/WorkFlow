import type { Node, Edge } from 'reactflow';
import { GraphParser } from './GraphParser';
import { Context } from './Context';
import { ExecutorManager } from './ExecutorManager';

export interface ExecutionResult {
  outputs: Record<string, any>;
  order: string[];
}

export class Runtime {
  static async run(nodes: Node[], edges: Edge[]): Promise<ExecutionResult> {
    const order = GraphParser.parse(nodes, edges);
    const context = new Context();

    for (const nodeId of order) {
      const node = nodes.find((n) => n.id === nodeId);
      if (!node) continue;

      // Gather input data from connected edges, keyed by targetHandle (port key)
      const inputEdges = edges.filter((e) => e.target === nodeId);
      const input: Record<string, any> = {};

      for (const edge of inputEdges) {
        const upstream = context.getOutput(edge.source);
        if (upstream) {
          // If targetHandle is specified, map upstream output to that port key
          // Otherwise, merge all upstream output
          if (edge.targetHandle) {
            // Map the relevant upstream port data
            if (edge.sourceHandle && upstream[edge.sourceHandle] !== undefined) {
              input[edge.targetHandle] = upstream[edge.sourceHandle];
            } else {
              // Merge all upstream data under the target port key
              Object.assign(input, upstream);
            }
          } else {
            Object.assign(input, upstream);
          }
        }
      }

      const output = await ExecutorManager.runNode(node.type!, node.data || {}, input);
      context.setOutput(nodeId, output);
    }

    return {
      outputs: context.getAllOutputs(),
      order,
    };
  }
}
