import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const GATE_FIELDS: NodeField[] = [
  { key: 'enabled', label: '启用', type: 'switch', defaultValue: false },
];

function GateNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🚪"
      label="Gate 门"
      nodeType="gate"
      fields={GATE_FIELDS}
    />
  );
}

export default memo(GateNode);
