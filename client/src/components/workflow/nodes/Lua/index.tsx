import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const LUA_FIELDS: NodeField[] = [
  { key: 'p4Path', label: 'P4 路径', placeholder: '//C7/.../file.lua' },
  { key: 'entryFunction', label: '入口函数', placeholder: '函数名（可选）' },
];

function LuaNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🌙"
      label="Lua"
      nodeType="lua"
      fields={LUA_FIELDS}
    />
  );
}

export default memo(LuaNode);
