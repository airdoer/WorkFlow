import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const IF_FIELDS: NodeField[] = [
  { key: 'expression', label: '条件表达式', placeholder: 'score >= 60（可选，有连线时可不填）' },
];

function IfNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🔀"
      label="If 条件"
      nodeType="if"
      fields={IF_FIELDS}
    />
  );
}

export default memo(IfNode);
