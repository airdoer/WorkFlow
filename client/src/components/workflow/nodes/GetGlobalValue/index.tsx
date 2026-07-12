import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const GET_GLOBAL_FIELDS: NodeField[] = [
  { key: 'key', label: 'Key', type: 'text', required: true, placeholder: '全局键名', linkedPortKey: 'keyIn' },
];

function GetGlobalValueNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="📥"
      label="GetGlobal"
      nodeType="getglobalvalue"
      fields={GET_GLOBAL_FIELDS}
    />
  );
}

export default memo(GetGlobalValueNode);
