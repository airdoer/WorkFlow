import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const LOOKUP_FIELDS: NodeField[] = [
  { key: 'key', label: '查找键', placeholder: '要查找的 key', required: true },
];

function LookupNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🔎"
      label="Lookup 查找"
      nodeType="lookup"
      fields={LOOKUP_FIELDS}
    />
  );
}

export default memo(LookupNode);
