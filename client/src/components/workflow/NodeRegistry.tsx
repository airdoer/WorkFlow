import React from 'react';
import type { NodeTypes } from 'reactflow';
import P4FileNode from './nodes/P4File';
import ExcelNode from './nodes/Excel';
import LuaNode from './nodes/Lua';
import JsonNode from './nodes/Json';
import PromptNode from './nodes/Prompt';
import P4FileIcon from './nodes/P4File/icon';
import ExcelIcon from './nodes/Excel/icon';
import LuaIcon from './nodes/Lua/icon';
import JsonIcon from './nodes/Json/icon';
import PromptIcon from './nodes/Prompt/icon';

export const nodeTypes: NodeTypes = {
  p4file: P4FileNode,
  excel: ExcelNode,
  lua: LuaNode,
  json: JsonNode,
  prompt: PromptNode,
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
  // Renderers
  { type: 'excel', label: 'Excel', icon: <ExcelIcon />, category: '渲染器', description: '接收文件内容，以表格形式渲染 Excel 数据' },
  { type: 'json', label: 'JSON', icon: <JsonIcon />, category: '渲染器', description: '接收文件内容，以 JSON 树形式渲染数据' },
  { type: 'lua', label: 'Lua', icon: <LuaIcon />, category: '渲染器', description: '接收文件内容，以语法高亮形式渲染 Lua 代码' },
  // AI
  { type: 'prompt', label: 'Prompt', icon: <PromptIcon />, category: 'AI', description: '使用 LLM 处理输入，生成文本输出' },
];

export function getNodeRegistry(type: string): NodeRegistryEntry | undefined {
  return nodeRegistryList.find((n) => n.type === type);
}
