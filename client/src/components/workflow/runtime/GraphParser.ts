import type { Node, Edge } from 'reactflow';

export class GraphParser {
  static parse(nodes: Node[], edges: Edge[]): string[] {
    const adj: Record<string, string[]> = {};
    const inDegree: Record<string, number> = {};
    const nodeMap: Record<string, any> = {};

    for (const node of nodes) {
      adj[node.id] = [];
      inDegree[node.id] = 0;
      nodeMap[node.id] = node;
    }

    for (const edge of edges) {
      const src = edge.source;
      const tgt = edge.target;
      if (adj[src] && inDegree[tgt] !== undefined) {
        adj[src].push(tgt);
        inDegree[tgt]++;
      }
    }

    const queue: string[] = [];
    for (const nid of Object.keys(inDegree)) {
      if (inDegree[nid] === 0) queue.push(nid);
    }

    const order: string[] = [];
    while (queue.length > 0) {
      const nid = queue.shift()!;
      order.push(nid);
      for (const neighbor of adj[nid]) {
        inDegree[neighbor]--;
        if (inDegree[neighbor] === 0) queue.push(neighbor);
      }
    }

    if (order.length !== nodes.length) {
      throw new Error('工作流中存在循环依赖');
    }

    return order;
  }
}
