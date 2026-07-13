import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const FLATTEN_FIELDS: NodeField[] = [];

function FlattenNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="📐"
      label="Flatten 展平"
      nodeType="flatten"
      fields={FLATTEN_FIELDS}
    />
  );
}

export default memo(FlattenNode);
