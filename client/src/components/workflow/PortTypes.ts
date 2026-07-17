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
  'file-content': ['file-content', 'string', 'text', 'any', 'object'],
  'file-path': ['file-path', 'string', 'any'],
  'any': ['file-content', 'file-path', 'any', 'text', 'table-data', 'json-data', 'boolean', 'string', 'number', 'json-path', 'list', 'object'],
  'text': ['text', 'any', 'string', 'file-content'],
  'table-data': ['table-data', 'any', 'list'],
  'json-data': ['json-data', 'any', 'object', 'list'],
  'boolean': ['boolean', 'any'],
  'string': ['string', 'any', 'text', 'file-content', 'file-path'],
  'number': ['number', 'any'],
  'json-path': ['json-path', 'string', 'any'],
  // New types for abstract data nodes
  'list': ['list', 'any', 'table-data', 'json-data', 'object'],
  'object': ['object', 'any', 'json-data', 'list', 'string', 'file-content'],
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
  // ===== Data Source =====
  p4file: [
    { key: 'p4Path', label: 'P4 路径', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'fileContent', label: '文件内容', type: 'file-content', direction: 'output' },
  ],
  excelsearch: [
    { key: 'fileContent', label: '文件内容', type: 'file-content', direction: 'output' },
    { key: 'localPath',   label: '本地路径', type: 'string',       direction: 'output' },
    { key: 'fileName',    label: '文件名',   type: 'string',       direction: 'output' },
    { key: 'sheetNames',  label: 'Sheet列表', type: 'any',         direction: 'output' },
  ],
  http: [
    { key: 'url', label: 'URL', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'body', label: 'Body', type: 'any', direction: 'input' },
    { key: 'response', label: '响应', type: 'any', direction: 'output' },
    { key: 'statusCode', label: '状态码', type: 'number', direction: 'output' },
  ],
  redis: [
    { key: 'key', label: 'Key', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'value', label: 'Value', type: 'any', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '结果', type: 'any', direction: 'output' },
    { key: 'success', label: '成功与否', type: 'boolean', direction: 'output' },
  ],
  file: [
    { key: 'path', label: '文件路径', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'content', label: '文件内容', type: 'file-content', direction: 'output' },
    { key: 'size', label: '文件大小', type: 'number', direction: 'output' },
  ],

  // ===== Renderers =====
  excel: [
    { key: 'fileContent', label: '文件内容',  type: 'file-content', direction: 'input' },
    { key: 'tableData',   label: '表格数据',  type: 'table-data',   direction: 'input',  maxConnections: 1 },
    { key: 'sheetName',   label: 'Sheet名',   type: 'string',       direction: 'input',  maxConnections: 1 },
    { key: 'tableData',      label: '表格数据',  type: 'table-data',   direction: 'output' },
    { key: 'rows',           label: '行数据',    type: 'list',          direction: 'output' },
    { key: 'columns',        label: '列名列表',  type: 'list',          direction: 'output' },
    { key: 'selectedRows',   label: '选中行',    type: 'any',           direction: 'output' },
    { key: 'selectedCols',   label: '选中列',    type: 'any',           direction: 'output' },
    { key: 'selectedValues', label: '选中值',    type: 'any',           direction: 'output' },
  ],
  json: [
    { key: 'fileContent', label: 'JSON String', type: 'string', direction: 'input' },
    { key: 'jsonPath', label: 'JSON Path', type: 'json-path', direction: 'input' },
    { key: 'jsonData', label: 'JSON 数据', type: 'json-data', direction: 'output' },
    { key: 'jsonStr', label: 'JSON String', type: 'string', direction: 'output' },
  ],
  lua: [
    { key: 'fileContent', label: '文件内容', type: 'file-content', direction: 'input' },
    { key: 'textOutput', label: '文本输出', type: 'text', direction: 'output' },
  ],
  table: [
    { key: 'tableInput', label: '数据输入', type: 'any',        direction: 'input',  maxConnections: 1 },
    { key: 'success',    label: '成功与否', type: 'boolean',    direction: 'output' },
    { key: 'tables',     label: '表格数据', type: 'table-data', direction: 'output' },
  ],
  diff: [
    { key: 'contentA', label: '内容1', type: 'any', direction: 'input' },
    { key: 'contentB', label: '内容2', type: 'any', direction: 'input' },
    { key: 'isSame', label: '是否相同', type: 'boolean', direction: 'output' },
  ],

  // ===== Collection =====
  map: [
    { key: 'list', label: '列表', type: 'list', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '结果列表', type: 'list', direction: 'output' },
  ],
  filter: [
    { key: 'list', label: '列表', type: 'list', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '结果列表', type: 'list', direction: 'output' },
  ],
  reduce: [
    { key: 'list', label: '列表', type: 'list', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '结果', type: 'any', direction: 'output' },
  ],
  sort: [
    { key: 'list', label: '列表', type: 'list', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '结果列表', type: 'list', direction: 'output' },
  ],
  join: [
    { key: 'source1', label: '数据源1', type: 'object', direction: 'input', maxConnections: 1 },
    { key: 'source2', label: '数据源2', type: 'object', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '合并结果', type: 'list', direction: 'output' },
  ],
  lookup: [
    { key: 'source', label: '数据源', type: 'object', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '查找结果', type: 'any', direction: 'output' },
    { key: 'found', label: '是否找到', type: 'boolean', direction: 'output' },
  ],
  split: [
    { key: 'list', label: '列表', type: 'list', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '结果列表', type: 'list', direction: 'output' },
  ],
  distinct: [
    { key: 'list', label: '列表', type: 'list', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '结果列表', type: 'list', direction: 'output' },
  ],
  flatten: [
    { key: 'list', label: '嵌套列表', type: 'list', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '展平列表', type: 'list', direction: 'output' },
  ],
  groupby: [
    { key: 'list', label: '列表', type: 'list', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '分组结果', type: 'object', direction: 'output' },
  ],
  mergeobject: [
    { key: 'source', label: '源对象', type: 'object', direction: 'input', maxConnections: 1 },
    { key: 'overrides', label: '覆盖对象', type: 'object', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '合并结果', type: 'object', direction: 'output' },
  ],

  // ===== Builders =====
  listbuilder: [
    { key: 'item1', label: '元素1', type: 'any', direction: 'input', maxConnections: 1 },
    { key: 'item2', label: '元素2', type: 'any', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '列表', type: 'list', direction: 'output' },
  ],
  objectbuilder: [
    { key: 'value_1', label: '值1', type: 'any', direction: 'input', maxConnections: 1 },
    { key: 'value_2', label: '值2', type: 'any', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '对象', type: 'object', direction: 'output' },
  ],
  dictbuilder: [
    { key: 'value_1', label: '值1', type: 'any', direction: 'input', maxConnections: 1 },
    { key: 'value_2', label: '值2', type: 'any', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '字典', type: 'object', direction: 'output' },
  ],

  // ===== Expression =====
  calculate: [
    { key: 'price', label: '价格', type: 'number', direction: 'input', maxConnections: 1 },
    { key: 'count', label: '数量', type: 'number', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '计算结果', type: 'number', direction: 'output' },
  ],
  template: [
    { key: 'list', label: '列表数据', type: 'list', direction: 'input', maxConnections: 1 },
    { key: 'name', label: '名称', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'count', label: '数量', type: 'number', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '渲染结果', type: 'string', direction: 'output' },
  ],
  condition: [
    { key: 'score', label: '分数', type: 'number', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '判断结果', type: 'boolean', direction: 'output' },
    { key: 'true', label: 'True值', type: 'any', direction: 'output' },
    { key: 'false', label: 'False值', type: 'any', direction: 'output' },
  ],

  // ===== AI =====
  prompt: [
    { key: 'context', label: '上下文', type: 'any', direction: 'input' },
    { key: 'result', label: '结果', type: 'text', direction: 'output' },
  ],
  llm: [
    { key: 'message', label: '消息', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'systemPrompt', label: '系统提示', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'response', label: '回复', type: 'text', direction: 'output' },
    { key: 'usage', label: 'Token用量', type: 'object', direction: 'output' },
  ],

  // ===== Control Flow =====
  if: [
    { key: 'condition', label: '条件', type: 'boolean', direction: 'input', maxConnections: 1 },
    { key: 'trueValue', label: 'True值', type: 'any', direction: 'input', maxConnections: 1 },
    { key: 'falseValue', label: 'False值', type: 'any', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '输出值', type: 'any', direction: 'output' },
    { key: 'branch', label: '分支', type: 'string', direction: 'output' },
  ],
  loop: [
    { key: 'list', label: '列表', type: 'list', direction: 'input', maxConnections: 1 },
    { key: 'condition', label: '循环条件', type: 'boolean', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '循环结果', type: 'list', direction: 'output' },
    { key: 'iterations', label: '迭代次数', type: 'number', direction: 'output' },
  ],
  switch: [
    { key: 'value', label: '输入值', type: 'any', direction: 'input', maxConnections: 1 },
    { key: 'case1', label: '分支1', type: 'any', direction: 'output' },
    { key: 'case2', label: '分支2', type: 'any', direction: 'output' },
    { key: 'default', label: '默认', type: 'any', direction: 'output' },
  ],
  boolgate: [
    { key: 'valueIn', label: '布尔输入', type: 'boolean', direction: 'input', maxConnections: 1 },
    { key: 'value', label: '通过结果', type: 'boolean', direction: 'output' },
  ],

  // ===== Basic Types =====
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

  // ===== Tool =====
  c7server: [
    { key: 'serverName', label: '服务器名', type: 'string', direction: 'output' },
  ],
  kdip: [
    { key: 'serverName', label: '服务器名', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'username', label: '用户名', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'success', label: '执行结果', type: 'boolean', direction: 'output' },
    { key: 'result', label: '结果内容', type: 'any', direction: 'output' },
  ],
  kimnotify: [
    { key: 'username', label: '用户名', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'groupId', label: 'GroupId', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'message', label: '消息内容', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'success', label: '发送结果', type: 'boolean', direction: 'output' },
  ],
  cron: [
    { key: 'valueIn', label: '输入值', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'trigger', label: '触发信号', type: 'any', direction: 'output' },
  ],
  setglobalvalue: [
    { key: 'keyIn', label: 'Key', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'valueIn', label: 'Value', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'success', label: '成功与否', type: 'boolean', direction: 'output' },
  ],
  getglobalvalue: [
    { key: 'keyIn', label: 'Key', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'success', label: '成功与否', type: 'boolean', direction: 'output' },
    { key: 'value', label: '值', type: 'string', direction: 'output' },
  ],
  seal: [
    { key: 'serverName', label: '服务器名', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'success', label: '执行结果', type: 'boolean', direction: 'output' },
    { key: 'taskUrl', label: '任务链接', type: 'string', direction: 'output' },
    { key: 'taskId', label: '任务ID', type: 'string', direction: 'output' },
  ],
  format: [
    // Static: default str1 input + result output.
    // Dynamic input ports are generated from variables[] via overridePorts.
    { key: 'str1', label: 'str1', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '结果', type: 'string', direction: 'output' },
  ],
  servercommand: [
    { key: 'command', label: '指令', type: 'string', direction: 'input', maxConnections: 1 },
    { key: 'result', label: '结果', type: 'string', direction: 'output' },
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
