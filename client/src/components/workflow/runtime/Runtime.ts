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

      const inputEdges = edges.filter((e) => e.target === nodeId);
      const input: Record<string, any> = {};
      for (const edge of inputEdges) {
        const upstream = context.getOutput(edge.source);
        if (upstream) Object.assign(input, upstream);
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
