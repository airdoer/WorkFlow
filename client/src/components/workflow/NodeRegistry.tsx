import { type PortDefinition } from './PortTypes';
import { getNodePorts } from './PortTypes';

// Node component imports
import BoolNode from './nodes/Bool';
import BoolGateNode from './nodes/BoolGate';
import GateNode from './nodes/Gate';
import C7ServerNode from './nodes/C7Server';
import CronNode from './nodes/Cron';
import DiffNode from './nodes/Diff';
import ExcelNode from './nodes/Excel';
import ExcelSearchNode from './nodes/ExcelSearch';
import GetGlobalValueNode from './nodes/GetGlobalValue';
import JsonNode from './nodes/Json';
import KimNotifyNode from './nodes/KimNotify';
import LuaNode from './nodes/Lua';
import NumberNode from './nodes/Number';
import P4FileNode from './nodes/P4File';
import PromptNode from './nodes/Prompt';
import SetGlobalValueNode from './nodes/SetGlobalValue';
import StringNode from './nodes/String';
import TableNode from './nodes/Table';
import KdipNode from './nodes/Jenkins';
// New node components
import MapNode from './nodes/Map';
import FilterNode from './nodes/Filter';
import ReduceNode from './nodes/Reduce';
import SortNode from './nodes/Sort';
import JoinNode from './nodes/Join';
import LookupNode from './nodes/Lookup';
import SplitNode from './nodes/Split';
import DistinctNode from './nodes/Distinct';
import FlattenNode from './nodes/Flatten';
import GroupByNode from './nodes/GroupBy';
import MergeObjectNode from './nodes/MergeObject';
import SealNode from './nodes/Seal';
import FormatNode from './nodes/Format';
import ServerCommandNode from './nodes/ServerCommand';
import JenkinsDeployNode from './nodes/JenkinsDeploy';
import ListBuilderNode from './nodes/ListBuilder';
import ObjectBuilderNode from './nodes/ObjectBuilder';
import DictBuilderNode from './nodes/DictBuilder';
import CalculateNode from './nodes/Calculate';
import TemplateNode from './nodes/Template';
import ConditionNode from './nodes/Condition';
import IfNode from './nodes/If';
import LoopNode from './nodes/Loop';
import SwitchNode from './nodes/Switch';
import HTTPNode from './nodes/HTTP';
import RedisNode from './nodes/Redis';
import FileNode from './nodes/File';
import LLMNode from './nodes/LLM';

/**
 * React Flow nodeTypes mapping — each key must match the nodeType string
 * used in the node data and the registry above.
 */
export const nodeTypes = {
  // Original
  bool: BoolNode,
  boolgate: BoolGateNode,
  gate: GateNode,
  c7server: C7ServerNode,
  cron: CronNode,
  diff: DiffNode,
  excel: ExcelNode,
  excelsearch: ExcelSearchNode,
  getglobalvalue: GetGlobalValueNode,
  json: JsonNode,
  kimnotify: KimNotifyNode,
  lua: LuaNode,
  number: NumberNode,
  p4file: P4FileNode,
  prompt: PromptNode,
  setglobalvalue: SetGlobalValueNode,
  string: StringNode,
  table: TableNode,
  kdip: KdipNode,
  // Collection
  map: MapNode,
  filter: FilterNode,
  reduce: ReduceNode,
  sort: SortNode,
  join: JoinNode,
  lookup: LookupNode,
  split: SplitNode,
  distinct: DistinctNode,
  flatten: FlattenNode,
  groupby: GroupByNode,
  mergeobject: MergeObjectNode,
  seal: SealNode,
  format: FormatNode,
  servercommand: ServerCommandNode,
  jenkinsdeploy: JenkinsDeployNode,
  // Builders
  listbuilder: ListBuilderNode,
  objectbuilder: ObjectBuilderNode,
  dictbuilder: DictBuilderNode,
  // Expression
  calculate: CalculateNode,
  template: TemplateNode,
  condition: ConditionNode,
  // AI
  llm: LLMNode,
  // Control Flow
  if: IfNode,
  loop: LoopNode,
  switch: SwitchNode,
  // Data Source
  http: HTTPNode,
  redis: RedisNode,
  file: FileNode,
};

/**
 * Category definitions for the 9-category system.
 */
export interface NodeCategory {
  id: string;
  name: string;
  color: string;
  icon?: string;
  order: number;
}

export const NODE_CATEGORIES: NodeCategory[] = [
  { id: 'datasource', name: '数据源', color: '#1890ff', order: 1 },
  { id: 'collection', name: '集合处理', color: '#13c2c2', order: 2 },
  { id: 'builder', name: '构建器', color: '#fa8c16', order: 3 },
  { id: 'expression', name: '表达式', color: '#722ed1', order: 4 },
  { id: 'ai', name: 'AI', color: '#eb2f96', order: 5 },
  { id: 'controlflow', name: '流程控制', color: '#52c41a', order: 6 },
  { id: 'basic', name: '基础值', color: '#595959', order: 7 },
  { id: 'renderer', name: '渲染器', color: '#fa541c', order: 8 },
  { id: 'tool', name: '工具', color: '#a0d911', order: 9 },
];

/**
 * Node type registry with category assignment.
 */
export interface NodeRegistryEntry {
  type: string;
  name: string;
  category: string;
  description?: string;
  icon?: string;
}

export const NODE_REGISTRY: NodeRegistryEntry[] = [
  // ===== 1. Data Source =====
  { type: 'p4file', name: 'P4 文件', category: 'datasource', description: 'P4 文件同步 + 输出' },
  { type: 'http', name: 'HTTP 请求', category: 'datasource', description: 'HTTP GET/POST 请求' },
  { type: 'redis', name: 'Redis', category: 'datasource', description: 'Redis 读写' },
  { type: 'file', name: '文件', category: 'datasource', description: '本地文件读取' },
  { type: 'excelsearch', name: 'Excel 搜索', category: 'datasource', description: 'Excel 文件选择器' },

  // ===== 2. Collection =====
  { type: 'map', name: 'Map 映射', category: 'collection', description: '对列表每个元素应用表达式' },
  { type: 'filter', name: 'Filter 过滤', category: 'collection', description: '过滤列表元素' },
  { type: 'reduce', name: 'Reduce 归约', category: 'collection', description: '将列表归约为单值' },
  { type: 'sort', name: 'Sort 排序', category: 'collection', description: '排序列表' },
  { type: 'join', name: 'Join 合并', category: 'collection', description: '按键/按位置合并数据源' },
  { type: 'lookup', name: 'Lookup 查找', category: 'collection', description: '按键查找' },
  { type: 'split', name: 'Split 拆分', category: 'collection', description: '拆分列表' },
  { type: 'distinct', name: 'Distinct 去重', category: 'collection', description: '去除重复元素' },
  { type: 'flatten', name: 'Flatten 展平', category: 'collection', description: '展平嵌套列表' },
  { type: 'groupby', name: 'GroupBy 分组', category: 'collection', description: '按字段分组' },
  { type: 'mergeobject', name: 'Merge 对象合并', category: 'collection', description: '合并/覆盖对象键值' },

  // ===== 3. Builders =====
  { type: 'listbuilder', name: '列表构建', category: 'builder', description: '从多个输入端口构建列表' },
  { type: 'objectbuilder', name: '对象构建', category: 'builder', description: '从键值对构建对象' },
  { type: 'dictbuilder', name: '字典构建', category: 'builder', description: '从键值对构建字典' },

  // ===== 4. Expression =====
  { type: 'calculate', name: '计算', category: 'expression', description: '数学计算表达式' },
  { type: 'template', name: '模板', category: 'expression', description: '模板字符串插值' },
  { type: 'format', name: 'Format 格式化', category: 'expression', description: '字符串格式化拼接（如URL）' },
  { type: 'servercommand', name: 'ServerCommand 指令', category: 'tool', description: '服务端 Lua 指令生成' },
  { type: 'condition', name: '条件', category: 'expression', description: '条件表达式' },

  // ===== 5. AI =====
  { type: 'prompt', name: 'Prompt', category: 'ai', description: 'LLM Prompt + 变量插值' },
  { type: 'llm', name: 'LLM', category: 'ai', description: '原始 LLM 调用' },

  // ===== 6. Control Flow =====
  { type: 'if', name: 'If 条件', category: 'controlflow', description: '条件分支（True/False 双输出）' },
  { type: 'loop', name: 'Loop 循环', category: 'controlflow', description: '循环迭代' },
  { type: 'switch', name: 'Switch 开关', category: 'controlflow', description: '多路分支' },
  { type: 'boolgate', name: 'BoolGate 门控', category: 'controlflow', description: '布尔门控（False 时中断）' },
  { type: 'gate', name: 'Gate 门', category: 'controlflow', description: '条件门控（enabled=true 时透传 value）' },

  // ===== 7. Basic Types =====
  { type: 'string', name: 'String 字符串', category: 'basic', description: '字符串值' },
  { type: 'bool', name: 'Bool 布尔', category: 'basic', description: '布尔值' },
  { type: 'number', name: 'Number 数值', category: 'basic', description: '数值' },

  // ===== 8. Renderers =====
  { type: 'excel', name: 'Excel', category: 'renderer', description: 'Excel 表格渲染' },
  { type: 'json', name: 'JSON', category: 'renderer', description: 'JSON 数据渲染' },
  { type: 'lua', name: 'Lua', category: 'renderer', description: 'Lua 脚本执行' },
  { type: 'table', name: 'Table', category: 'renderer', description: '表格数据渲染' },
  { type: 'diff', name: 'Diff', category: 'renderer', description: '差异对比' },

  // ===== 9. Tool =====
  { type: 'c7server', name: 'C7 服务器', category: 'tool', description: '服务器选择器' },
  { type: 'seal', name: 'Seal 海豹', category: 'tool', description: 'SOPS 海豹部署任务' },
  { type: 'jenkinsdeploy', name: 'Jenkins 部署', category: 'tool', description: '触发 Jenkins 打包/热更任务' },
  { type: 'kdip', name: 'KDIP', category: 'tool', description: 'KDIP 部署' },
  { type: 'kimnotify', name: 'Kim 通知', category: 'tool', description: 'Kim 消息通知' },
  { type: 'cron', name: 'Cron 定时', category: 'tool', description: '定时触发器' },
  { type: 'setglobalvalue', name: '设置全局值', category: 'tool', description: '设置全局存储值' },
  { type: 'getglobalvalue', name: '获取全局值', category: 'tool', description: '获取全局存储值' },
];

/**
 * Get all node types grouped by category.
 */
export function getNodesByCategory(): Record<string, NodeRegistryEntry[]> {
  const grouped: Record<string, NodeRegistryEntry[]> = {};
  for (const entry of NODE_REGISTRY) {
    if (!grouped[entry.category]) {
      grouped[entry.category] = [];
    }
    grouped[entry.category].push(entry);
  }
  return grouped;
}

/**
 * Get a node registry entry by type.
 */
export function getNodeEntry(type: string): NodeRegistryEntry | undefined {
  return NODE_REGISTRY.find((e) => e.type === type);
}

/**
 * Get the category for a node type.
 */
export function getNodeCategory(type: string): string {
  const entry = getNodeEntry(type);
  return entry?.category ?? 'tool';
}

/**
 * Get the display name for a node type.
 */
export function getNodeName(type: string): string {
  const entry = getNodeEntry(type);
  return entry?.name ?? type;
}

/**
 * Check if a node type exists in the registry.
 */
export function isRegisteredNodeType(type: string): boolean {
  return NODE_REGISTRY.some((e) => e.type === type);
}

/**
 * Get all registered node types.
 */
export function getAllNodeTypes(): string[] {
  return NODE_REGISTRY.map((e) => e.type);
}

/**
 * Filter node registry by visible node types (permission-based).
 * Returns only entries whose type is in the visible list.
 * If visibleTypes is undefined or empty, returns all (no filtering — for admin or when permissions not loaded).
 */
export function filterByPermission(visibleTypes: string[] | undefined): NodeRegistryEntry[] {
  if (!visibleTypes || visibleTypes.length === 0) return NODE_REGISTRY;
  return NODE_REGISTRY.filter((e) => visibleTypes.includes(e.type));
}

// ── Backward-compatible exports for Toolbox.tsx and PropertyPanel.tsx ──

/**
 * Toolbox-compatible node registry list.
 * Each entry has { nodeType, label, icon, category, description }.
 */
export const nodeRegistryList = NODE_REGISTRY.map((e) => {
  const iconStr = getNodeIcon(e.type);
  return {
    type: e.type,
    label: e.name,
    icon: iconStr,
    category: getCategoryName(e.category),
    description: e.description || '',
  };
});

/**
 * PropertyPanel-compatible: get a registry entry by node type.
 * Returns { label, icon, category, description } or null.
 */
export function getNodeRegistry(nodeType: string): {
  label: string;
  icon: string;
  category: string;
  description: string;
} | null {
  const entry = getNodeEntry(nodeType);
  if (!entry) return null;
  return {
    label: entry.name,
    icon: getNodeIcon(nodeType),
    category: getCategoryName(entry.category),
    description: entry.description || '',
  };
}

/** Icon map for all node types */
function getNodeIcon(nodeType: string): string {
  const iconMap: Record<string, string> = {
    p4file: '📁', http: '🌐', redis: '🗄️', file: '📄', excelsearch: '🔍',
    map: '🔄', filter: '🔍', reduce: '📊', sort: '🔢', join: '🔗',
    lookup: '🔎', split: '✂️', distinct: '🎯', flatten: '📐', groupby: '📂', mergeobject: '🔧',
    listbuilder: '📦', objectbuilder: '🏗️', dictbuilder: '📖',
    calculate: '🧮', template: '📝', condition: '❓',
    prompt: '🤖', llm: '🤖',
    if: '🔀', loop: '🔁', switch: '🎛️', boolgate: '🚦', gate: '🚪',
    bool: '🔘', string: '📝', number: '🔢',
    excel: '📊', json: '📋', lua: '🌙', table: '📊', diff: '🔄',
    c7server: '🖥️', seal: '🐾', jenkinsdeploy: '🚀', format: '🔤', kdip: '⚙️', kimnotify: '🔔', cron: '⏰',
    setglobalvalue: '💾', getglobalvalue: '📖',
  };
  return iconMap[nodeType] || '🔹';
}

/** Get Chinese category name from category ID */
function getCategoryName(categoryId: string): string {
  const cat = NODE_CATEGORIES.find((c) => c.id === categoryId);
  return cat?.name ?? categoryId;
}
