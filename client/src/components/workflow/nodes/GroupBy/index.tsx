import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const GROUPBY_FIELDS: NodeField[] = [
  { key: 'expression', label: '分组表达式', type: 'textarea', rows: 2, placeholder: 'item.category', required: true },
];

function GroupByNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="📂"
      label="GroupBy 分组"
      nodeType="groupby"
      fields={GROUPBY_FIELDS}
    />
  );
}

export default memo(GroupByNode);
