import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const SET_GLOBAL_FIELDS: NodeField[] = [
  { key: 'key', label: 'Key', type: 'text', required: true, placeholder: '全局键名', linkedPortKey: 'keyIn' },
  { key: 'value', label: 'Value', type: 'text', required: true, placeholder: '全局值', linkedPortKey: 'valueIn' },
];

function SetGlobalValueNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="📤"
      label="SetGlobal"
      nodeType="setglobalvalue"
      fields={SET_GLOBAL_FIELDS}
    />
  );
}

export default memo(SetGlobalValueNode);
