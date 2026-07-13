import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const FILTER_FIELDS: NodeField[] = [
  { key: 'expression', label: '条件表达式', type: 'textarea', rows: 2, placeholder: 'item > 2 或 item.active == true', required: true },
];

function FilterNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🔍"
      label="Filter 过滤"
      nodeType="filter"
      fields={FILTER_FIELDS}
    />
  );
}

export default memo(FilterNode);
