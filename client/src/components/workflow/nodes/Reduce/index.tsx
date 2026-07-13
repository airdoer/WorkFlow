import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const REDUCE_FIELDS: NodeField[] = [
  { key: 'expression', label: '归约表达式', type: 'textarea', rows: 2, placeholder: 'acc + item', required: true },
  { key: 'initialValue', label: '初始值', placeholder: '0 或 ""' },
];

function ReduceNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="📊"
      label="Reduce 归约"
      nodeType="reduce"
      fields={REDUCE_FIELDS}
    />
  );
}

export default memo(ReduceNode);
