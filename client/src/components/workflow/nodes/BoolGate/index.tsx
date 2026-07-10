import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const BOOLGATE_FIELDS: NodeField[] = [
  // 无手动配置字段，值完全由连线提供
];

function BoolGateNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🚦"
      label="Bool 门控"
      nodeType="boolgate"
      fields={BOOLGATE_FIELDS}
    />
  );
}

export default memo(BoolGateNode);
