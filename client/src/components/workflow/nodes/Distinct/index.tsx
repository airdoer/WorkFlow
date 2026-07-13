import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const DISTINCT_FIELDS: NodeField[] = [
  { key: 'key', label: '去重字段', placeholder: 'id（对象列表时使用）' },
];

function DistinctNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🎯"
      label="Distinct 去重"
      nodeType="distinct"
      fields={DISTINCT_FIELDS}
    />
  );
}

export default memo(DistinctNode);
