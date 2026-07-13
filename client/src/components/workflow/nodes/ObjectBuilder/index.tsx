import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const OBJECTBUILDER_FIELDS: NodeField[] = [
  { key: 'key1', label: '键1', placeholder: 'id' },
  { key: 'value1', label: '值1', placeholder: '1001' },
  { key: 'key2', label: '键2', placeholder: 'name' },
  { key: 'value2', label: '值2', placeholder: '宝刀' },
];

function ObjectBuilderNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🏗️"
      label="对象构建"
      nodeType="objectbuilder"
      fields={OBJECTBUILDER_FIELDS}
    />
  );
}

export default memo(ObjectBuilderNode);
