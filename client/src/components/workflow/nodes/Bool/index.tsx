import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import ValueNode from '../ValueNode';

function BoolNode({ data, id, selected }: NodeProps) {
  return (
    <ValueNode
      id={id}
      data={data as Record<string, unknown>}
      selected={!!selected}
      icon="🔘"
      label="Bool"
      nodeType="bool"
      valueKey="value"
      portColor="#eb2f96"
      inputType="boolean"
      outputPortKey="value"
      outputPortLabel="布尔值"
      inputPortKey="valueIn"
      inputPortLabel="输入值"
    />
  );
}

export default memo(BoolNode);
