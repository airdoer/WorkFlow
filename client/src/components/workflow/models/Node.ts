export interface NodeModel {
  id: string;
  type: string;
  data: Record<string, unknown>;
  position: { x: number; y: number };
}
