import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const LISTBUILDER_FIELDS: NodeField[] = [
  { key: 'item1', label: '元素1', placeholder: '值或连线' },
  { key: 'item2', label: '元素2', placeholder: '值或连线' },
];

function ListBuilderNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="📦"
      label="列表构建"
      nodeType="listbuilder"
      fields={LISTBUILDER_FIELDS}
    />
  );
}

export default memo(ListBuilderNode);
