import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const PROMPT_FIELDS: NodeField[] = [
  { key: 'prompt', label: '提示词', type: 'textarea', rows: 3, placeholder: '输入提示词，支持 {{nodeId.key}} 变量', required: true },
  { key: 'model', label: '模型', placeholder: 'qwen-plus' },
  { key: 'temperature', label: '温度', type: 'number', step: 0.1, placeholder: '0.7' },
];

function PromptNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🤖"
      label="Prompt"
      nodeType="prompt"
      fields={PROMPT_FIELDS}
    />
  );
}

export default memo(PromptNode);
