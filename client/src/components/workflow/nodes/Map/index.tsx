import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const MAP_FIELDS: NodeField[] = [
  { key: 'expression', label: '表达式', type: 'textarea', rows: 2, placeholder: 'item * 2 或 item.name', required: true },
];

function MapNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🔄"
      label="Map 映射"
      nodeType="map"
      fields={MAP_FIELDS}
    />
  );
}

export default memo(MapNode);
