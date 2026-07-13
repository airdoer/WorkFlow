import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const SWITCH_FIELDS: NodeField[] = [];

function SwitchNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🎛️"
      label="Switch 开关"
      nodeType="switch"
      fields={SWITCH_FIELDS}
    />
  );
}

export default memo(SwitchNode);
