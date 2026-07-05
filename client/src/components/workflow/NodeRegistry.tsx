import { FlowNodeRegistry } from '@flowgram.ai/free-layout-editor';
import { ExcelNodeRegistry } from './nodes/Excel';
import { LuaNodeRegistry } from './nodes/Lua';
import { JsonNodeRegistry } from './nodes/Json';
import { PromptNodeRegistry } from './nodes/Prompt';
import ExcelIcon from './nodes/Excel/icon';
import LuaIcon from './nodes/Lua/icon';
import JsonIcon from './nodes/Json/icon';
import PromptIcon from './nodes/Prompt/icon';

export interface NodeRegistryEntry {
  type: string;
  label: string;
  icon: React.ReactNode;
  registry: FlowNodeRegistry;
}

export const nodeRegistries: FlowNodeRegistry[] = [
  ExcelNodeRegistry,
  LuaNodeRegistry,
  JsonNodeRegistry,
  PromptNodeRegistry,
];

export const nodeRegistryList: NodeRegistryEntry[] = [
  { type: 'excel', label: 'Excel', icon: <ExcelIcon />, registry: ExcelNodeRegistry },
  { type: 'lua', label: 'Lua', icon: <LuaIcon />, registry: LuaNodeRegistry },
  { type: 'json', label: 'JSON', icon: <JsonIcon />, registry: JsonNodeRegistry },
  { type: 'prompt', label: 'Prompt', icon: <PromptIcon />, registry: PromptNodeRegistry },
];

export function getNodeRegistry(type: string): NodeRegistryEntry | undefined {
  return nodeRegistryList.find((n) => n.type === type);
}
