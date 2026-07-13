import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const SPLIT_FIELDS: NodeField[] = [
  { key: 'field', label: '拆分字段', placeholder: '按字段拆分（可选）' },
  { key: 'chunkSize', label: '分块大小', type: 'number', placeholder: '2' },
];

function SplitNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="✂️"
      label="Split 拆分"
      nodeType="split"
      fields={SPLIT_FIELDS}
    />
  );
}

export default memo(SplitNode);
