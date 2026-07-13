import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const CALCULATE_FIELDS: NodeField[] = [
  { key: 'expression', label: '计算表达式', type: 'textarea', rows: 2, placeholder: 'price * count * discount', required: true },
];

function CalculateNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🧮"
      label="计算"
      nodeType="calculate"
      fields={CALCULATE_FIELDS}
    />
  );
}

export default memo(CalculateNode);
