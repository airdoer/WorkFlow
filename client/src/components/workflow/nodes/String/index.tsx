import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import ValueNode from '../ValueNode';

function StringNode({ data, id, selected }: NodeProps) {
  return (
    <ValueNode
      id={id}
      data={data as Record<string, unknown>}
      selected={!!selected}
      icon="📝"
      label="String"
      nodeType="string"
      valueKey="value"
      portColor="#fa8c16"
      inputType="text"
      outputPortKey="value"
      outputPortLabel="字符串"
      inputPortKey="valueIn"
      inputPortLabel="输入值"
    />
  );
}

export default memo(StringNode);
