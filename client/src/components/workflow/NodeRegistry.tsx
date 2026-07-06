import React from 'react';
import type { NodeTypes } from 'reactflow';
import ExcelNode from './nodes/Excel';
import LuaNode from './nodes/Lua';
import JsonNode from './nodes/Json';
import PromptNode from './nodes/Prompt';
import ExcelIcon from './nodes/Excel/icon';
import LuaIcon from './nodes/Lua/icon';
import JsonIcon from './nodes/Json/icon';
import PromptIcon from './nodes/Prompt/icon';

export const nodeTypes: NodeTypes = {
  excel: ExcelNode,
  lua: LuaNode,
  json: JsonNode,
  prompt: PromptNode,
};

export interface NodeRegistryEntry {
  type: string;
  label: string;
  icon: React.ReactNode;
}

export const nodeRegistryList: NodeRegistryEntry[] = [
  { type: 'excel', label: 'Excel', icon: <ExcelIcon /> },
  { type: 'lua', label: 'Lua', icon: <LuaIcon /> },
  { type: 'json', label: 'JSON', icon: <JsonIcon /> },
  { type: 'prompt', label: 'Prompt', icon: <PromptIcon /> },
];

export function getNodeRegistry(type: string): NodeRegistryEntry | undefined {
  return nodeRegistryList.find((n) => n.type === type);
}
