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
  'file-content': ['file-content', 'string', 'text', 'any'],  // file-content is essentially a string
  'file-path': ['file-path', 'string', 'any'],  // file-path is also a string
  'any': ['file-content', 'file-path', 'any', 'text', 'table-data', 'json-data', 'boolean', 'string', 'number', 'json-path'],
  'text': ['text', 'any', 'string', 'file-content'],  // text accepts file-content too
  'table-data': ['table-data', 'any'],
  'json-data': ['json-data', 'any'],
  'boolean': ['boolean', 'any'],
  'string': ['string', 'any', 'text', 'file-content', 'file-path'],  // string is compatible with file-content/file-path
  'number': ['number', 'any'],
  'json-path': ['json-path', 'string', 'any'],
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
    { key: 'jsonPath', label: 'JSON Path', type: 'json-path', direction: 'input' },
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
  // Basic type nodes
  bool: [
    { key: 'valueIn', label: '输入值', type: 'boolean', direction: 'input', maxConnections: 1 },
    { key: 'value', label: '布尔值', type: 'boolean', direction: 'output' },
  ],
  string: [
    { key: 'valueIn', label: '输入值', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'value', label: '字符串', type: 'string', direction: 'output' },
  ],
  number: [
    { key: 'valueIn', label: '输入值', type: 'number', direction: 'input', maxConnections: 1 },
    { key: 'value', label: '数值', type: 'number', direction: 'output' },
  ],
  // Diff node — compares two strings, outputs isSame boolean
  diff: [
    { key: 'contentA', label: '内容1', type: 'string', direction: 'input' },
    { key: 'contentB', label: '内容2', type: 'string', direction: 'input' },
    { key: 'isSame', label: '是否相同', type: 'boolean', direction: 'output' },
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
