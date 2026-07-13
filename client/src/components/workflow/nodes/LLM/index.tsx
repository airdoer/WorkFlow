import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const LLM_FIELDS: NodeField[] = [
  { key: 'model', label: '模型', placeholder: 'qwen-plus' },
  { key: 'temperature', label: '温度', type: 'number', step: 0.1, placeholder: '0.7' },
  { key: 'maxTokens', label: '最大 Token', type: 'number', placeholder: '2048' },
  { key: 'systemPrompt', label: '系统提示词', type: 'textarea', rows: 2, placeholder: '可选' },
];

function LLMNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🤖"
      label="LLM"
      nodeType="llm"
      fields={LLM_FIELDS}
    />
  );
}

export default memo(LLMNode);
