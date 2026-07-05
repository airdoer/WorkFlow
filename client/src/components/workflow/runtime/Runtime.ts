import { GraphParser } from './GraphParser';
import { Context } from './Context';
import { ExecutorManager } from './ExecutorManager';
import type { WorkflowJSON } from '../types';

export interface ExecutionResult {
  outputs: Record<string, any>;
  order: string[];
}

export class Runtime {
  static async run(json: WorkflowJSON): Promise<ExecutionResult> {
    const order = GraphParser.parse(json);
    const context = new Context();

    for (const nodeId of order) {
      const node = json.nodes.find((n) => n.id === nodeId);
      if (!node) continue;

      const inputEdges = json.edges.filter((e) => e.targetNodeID === nodeId);
      const input: Record<string, any> = {};
      for (const edge of inputEdges) {
        const upstream = context.getOutput(edge.sourceNodeID);
        if (upstream) Object.assign(input, upstream);
      }

      const output = await ExecutorManager.runNode(node.type, node.data || {}, input);
      context.setOutput(nodeId, output);
    }

    return {
      outputs: context.getAllOutputs(),
      order,
    };
  }
}
