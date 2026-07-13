import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const CONDITION_FIELDS: NodeField[] = [
  { key: 'expression', label: '条件表达式', type: 'textarea', rows: 2, placeholder: 'score >= 60', required: true },
];

function ConditionNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="❓"
      label="条件"
      nodeType="condition"
      fields={CONDITION_FIELDS}
    />
  );
}

export default memo(ConditionNode);
