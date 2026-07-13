import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const LOOP_FIELDS: NodeField[] = [
  { key: 'mode', label: '循环模式', type: 'select', options: [
    { label: '遍历列表 (for_each)', value: 'for_each' },
    { label: '条件循环 (while)', value: 'while' },
    { label: '计数循环 (count)', value: 'count' },
  ], required: true },
  { key: 'maxIterations', label: '最大迭代', type: 'number', placeholder: '1000' },
  { key: 'count', label: '次数', type: 'number', placeholder: 'count 模式下使用' },
];

function LoopNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🔁"
      label="Loop 循环"
      nodeType="loop"
      fields={LOOP_FIELDS}
    />
  );
}

export default memo(LoopNode);
