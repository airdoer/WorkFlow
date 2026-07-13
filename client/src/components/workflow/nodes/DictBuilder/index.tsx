import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const DICTBUILDER_FIELDS: NodeField[] = [
  { key: 'key1', label: '键1', placeholder: '1001' },
  { key: 'value1', label: '值1', placeholder: '{"name":"宝刀","quality":5}' },
  { key: 'key2', label: '键2', placeholder: '1002' },
  { key: 'value2', label: '值2', placeholder: '{"name":"长剑","quality":3}' },
];

function DictBuilderNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="📖"
      label="字典构建"
      nodeType="dictbuilder"
      fields={DICTBUILDER_FIELDS}
    />
  );
}

export default memo(DictBuilderNode);
