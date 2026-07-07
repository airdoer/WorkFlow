/**
 * Port type system for workflow nodes.
 * Defines typed input/output ports with matching rules.
 * When source port type === target port type, the edge turns green with flowing animation.
 */

export type PortDirection = 'input' | 'output';

export interface PortDefinition {
  /** Unique key within the node */
  key: string;
  /** Display label */
  label: string;
  /** Port type for matching: source & target must share the same type to match */
  type: string;
  /** Direction: input (target handle) or output (source handle) */
  direction: PortDirection;
  /** Maximum number of connections (0 = unlimited) */
  maxConnections?: number;
}

/** Registry of all known port types and their compatibility */
export const PORT_TYPE_COMPATIBILITY: Record<string, string[]> = {
  'file-content': ['file-content', 'any'],
  'file-path': ['file-path', 'any'],
  'any': ['file-content', 'file-path', 'any', 'text', 'table-data', 'json-data'],
  'text': ['text', 'any'],
  'table-data': ['table-data', 'any'],
  'json-data': ['json-data', 'any'],
};

/**
 * Check if a source port type is compatible with a target port type.
 * Returns true if the types match directly or via compatibility registry.
 */
export function isPortTypeCompatible(sourceType: string, targetType: string): boolean {
  if (sourceType === targetType) return true;
  const compatible = PORT_TYPE_COMPATIBILITY[sourceType];
  if (compatible && compatible.includes(targetType)) return true;
  const compatibleReverse = PORT_TYPE_COMPATIBILITY[targetType];
  if (compatibleReverse && compatibleReverse.includes(sourceType)) return true;
  return false;
}

/** Get edge style based on port type compatibility */
export function getEdgeMatchStatus(
  sourcePortType?: string,
  targetPortType?: string,
): 'matched' | 'mismatched' | 'unknown' {
  if (!sourcePortType || !targetPortType) return 'unknown';
  return isPortTypeCompatible(sourcePortType, targetPortType) ? 'matched' : 'mismatched';
}

/**
 * Node port definitions by node type.
 * Each node type declares its input and output ports.
 */
export const NODE_PORT_DEFINITIONS: Record<string, PortDefinition[]> = {
  p4file: [
    { key: 'fileContent', label: '文件内容', type: 'file-content', direction: 'output' },
  ],
  excel: [
    { key: 'fileContent', label: '文件内容', type: 'file-content', direction: 'input' },
    { key: 'tableData', label: '表格数据', type: 'table-data', direction: 'output' },
  ],
  json: [
    { key: 'fileContent', label: '文件内容', type: 'file-content', direction: 'input' },
    { key: 'jsonData', label: 'JSON 数据', type: 'json-data', direction: 'output' },
  ],
  lua: [
    { key: 'fileContent', label: '文件内容', type: 'file-content', direction: 'input' },
    { key: 'textOutput', label: '文本输出', type: 'text', direction: 'output' },
  ],
  prompt: [
    { key: 'context', label: '上下文', type: 'any', direction: 'input' },
    { key: 'result', label: '结果', type: 'text', direction: 'output' },
  ],
};

export function getNodePorts(nodeType: string): PortDefinition[] {
  return NODE_PORT_DEFINITIONS[nodeType] || [];
}

export function getInputPorts(nodeType: string): PortDefinition[] {
  return getNodePorts(nodeType).filter((p) => p.direction === 'input');
}

export function getOutputPorts(nodeType: string): PortDefinition[] {
  return getNodePorts(nodeType).filter((p) => p.direction === 'output');
}
