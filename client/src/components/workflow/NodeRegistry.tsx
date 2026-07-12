import React from 'react';
import type { NodeTypes } from 'reactflow';
import P4FileNode from './nodes/P4File';
import ExcelNode from './nodes/Excel';
import LuaNode from './nodes/Lua';
import JsonNode from './nodes/Json';
import PromptNode from './nodes/Prompt';
import BoolNode from './nodes/Bool';
import StringNode from './nodes/String';
import NumberNode from './nodes/Number';
import DiffNode from './nodes/Diff';
import C7ServerNode from './nodes/C7Server';
import KdipNode from './nodes/Jenkins';
import KimNotifyNode from './nodes/KimNotify';
import BoolGateNode from './nodes/BoolGate';
import TableNode from './nodes/Table';
import ExcelSearchNode from './nodes/ExcelSearch';
import CronNode from './nodes/Cron';
import SetGlobalValueNode from './nodes/SetGlobalValue';
import GetGlobalValueNode from './nodes/GetGlobalValue';

import P4FileIcon from './nodes/P4File/icon';
import ExcelIcon from './nodes/Excel/icon';
import LuaIcon from './nodes/Lua/icon';
import JsonIcon from './nodes/Json/icon';
import PromptIcon from './nodes/Prompt/icon';
import BoolIcon from './nodes/Bool/icon';
import StringIcon from './nodes/String/icon';
import NumberIcon from './nodes/Number/icon';
import DiffIcon from './nodes/Diff/icon';
import C7ServerIcon from './nodes/C7Server/icon';
import KdipIcon from './nodes/Jenkins/icon';
import KimNotifyIcon from './nodes/KimNotify/icon';
import BoolGateIcon from './nodes/BoolGate/icon';
import TableIcon from './nodes/Table/icon';
import ExcelSearchIcon from './nodes/ExcelSearch/icon';
import CronIcon from './nodes/Cron/icon';
import SetGlobalValueIcon from './nodes/SetGlobalValue/icon';
import GetGlobalValueIcon from './nodes/GetGlobalValue/icon';

export const nodeTypes: NodeTypes = {
  p4file: P4FileNode,
  excel: ExcelNode,
  lua: LuaNode,
  json: JsonNode,
  prompt: PromptNode,
  bool: BoolNode,
  string: StringNode,
  number: NumberNode,
  diff: DiffNode,
  c7server: C7ServerNode,
  kdip: KdipNode,
  kimnotify: KimNotifyNode,
  boolgate: BoolGateNode,
  table: TableNode,
  excelsearch: ExcelSearchNode,
  cron: CronNode,
  setglobalvalue: SetGlobalValueNode,
  getglobalvalue: GetGlobalValueNode,
};

export interface NodeRegistryEntry {
  type: string;
  label: string;
  icon: React.ReactNode;
  category?: string;
  description?: string;
}

export const nodeRegistryList: NodeRegistryEntry[] = [
  // Data sources
  { type: 'p4file', label: 'P4 文件', icon: <P4FileIcon />, category: '数据源', description: '从 P4 获取文件内容，输出给下游渲染器' },
  { type: 'c7server', label: 'C7 服务器', icon: <C7ServerIcon />, category: '数据源', description: '从下拉列表选择 C7 服务器或服务器分组，输出服务器名' },
  // Renderers
  { type: 'excel', label: 'Excel', icon: <ExcelIcon />, category: '渲染器', description: '接收文件内容，以表格形式渲染 Excel 数据' },
  { type: 'json', label: 'JSON', icon: <JsonIcon />, category: '渲染器', description: '接收文件内容，以 JSON 树形式渲染数据；JSON Path 支持手动输入或连线提供' },
  { type: 'lua', label: 'Lua', icon: <LuaIcon />, category: '渲染器', description: '接收文件内容，以语法高亮形式渲染 Lua 代码' },
  // AI
  { type: 'prompt', label: 'Prompt', icon: <PromptIcon />, category: 'AI', description: '使用 LLM 处理输入，生成文本输出' },
  // Basic types
  { type: 'bool', label: 'Bool', icon: <BoolIcon />, category: '基础类型', description: '布尔值节点，可直接在节点上切换 true/false，或通过连线获取输入' },
  { type: 'string', label: 'String', icon: <StringIcon />, category: '基础类型', description: '字符串节点，可直接在节点上输入文本，或通过连线获取输入' },
  { type: 'number', label: 'Number', icon: <NumberIcon />, category: '基础类型', description: '数值节点，可直接在节点上输入数字，或通过连线获取输入' },
  // Tool
  { type: 'diff', label: 'Diff', icon: <DiffIcon />, category: '工具', description: '对比两个字符串的差异，输出 diff 结果和是否相同布尔值' },
  { type: 'kdip', label: 'KDIP', icon: <KdipIcon />, category: '工具', description: '在指定 C7 服务器上执行 KDIP 任务，输出成功与否及结果内容' },
  { type: 'kimnotify', label: 'Kim 通知', icon: <KimNotifyIcon />, category: '工具', description: '通过 Kim 机器人发送消息给用户或群组，输出发送结果' },
  { type: 'boolgate', label: 'Bool 门控', icon: <BoolGateIcon />, category: '工具', description: '当输入为 True 时放行执行后续节点，为 False 时报错中断' },
  // Renderers
  { type: 'table', label: 'Table 表格', icon: <TableIcon />, category: '渲染器', description: '接收上游数据，将数组/字典渲染为表格；数组→单表，字典→多表' },
  // Data sources
  { type: 'excelsearch', label: 'Excel 搜索', icon: <ExcelSearchIcon />, category: '数据源', description: '从预注册列表中选择 Excel 文件，输出文件内容供下游 Excel 节点使用' },
  // Trigger
  { type: 'cron', label: 'Cron 定时', icon: <CronIcon />, category: '触发器', description: '按 Cron 表达式定时触发下游节点执行，最低频率 1 分钟' },
  // Global storage
  { type: 'setglobalvalue', label: 'SetGlobal', icon: <SetGlobalValueIcon />, category: '全局存储', description: '向 Redis 写入全局键值对，输出执行成功与否' },
  { type: 'getglobalvalue', label: 'GetGlobal', icon: <GetGlobalValueIcon />, category: '全局存储', description: '从 Redis 读取全局键的值，输出成功与否和值' },
];

export function getNodeRegistry(type: string): NodeRegistryEntry | undefined {
  return nodeRegistryList.find((n) => n.type === type);
}
