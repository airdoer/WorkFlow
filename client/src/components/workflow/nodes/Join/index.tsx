import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const JOIN_FIELDS: NodeField[] = [
  { key: 'mode', label: '合并模式', type: 'select', options: [
    { label: '按字段合并 (SQL JOIN)', value: 'combine_by_field' },
    { label: '按键合并 (dict key)', value: 'combine_by_key' },
    { label: '按位置合并', value: 'combine_by_position' },
    { label: '追加合并', value: 'append' },
    { label: '配对合并', value: 'zip' },
  ], required: true },
  { key: 'joinField', label: '关联字段', type: 'text', placeholder: '共同字段名，如 装备ID',
    linkedPortKey: 'source1' },
  { key: 'joinType', label: 'Join 类型', type: 'select', options: [
    { label: 'Inner Join', value: 'inner' },
    { label: 'Left Join', value: 'left' },
    { label: 'Outer Join', value: 'outer' },
    { label: 'Right Join', value: 'right' },
  ], placeholder: 'inner' },
];

function JoinNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🔗"
      label="Join 合并"
      nodeType="join"
      fields={JOIN_FIELDS}
    />
  );
}

export default memo(JoinNode);
