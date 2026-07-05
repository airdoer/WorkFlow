export class Context {
  private outputs: Map<string, any> = new Map();

  getOutput(nodeId: string): any {
    return this.outputs.get(nodeId);
  }

  setOutput(nodeId: string, output: any): void {
    this.outputs.set(nodeId, output);
  }

  getAllOutputs(): Record<string, any> {
    return Object.fromEntries(this.outputs);
  }
}
