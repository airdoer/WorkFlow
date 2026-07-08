import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import ValueNode from '../ValueNode';

function NumberNode({ data, id, selected }: NodeProps) {
  return (
    <ValueNode
      id={id}
      data={data as Record<string, unknown>}
      selected={!!selected}
      icon="🔢"
      label="Number"
      nodeType="number"
      valueKey="value"
      portColor="#13c2c2"
      inputType="number"
      outputPortKey="value"
      outputPortLabel="数值"
      inputPortKey="valueIn"
      inputPortLabel="输入值"
    />
  );
}

export default memo(NumberNode);
