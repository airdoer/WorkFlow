import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const HTTP_FIELDS: NodeField[] = [
  { key: 'url', label: 'URL', placeholder: 'https://api.example.com/data', required: true },
  { key: 'method', label: '方法', type: 'select', options: [
    { label: 'GET', value: 'GET' },
    { label: 'POST', value: 'POST' },
  ], placeholder: 'GET' },
  { key: 'headers', label: 'Headers', type: 'textarea', rows: 2, placeholder: '{"Content-Type": "application/json"}' },
  { key: 'body', label: 'Body', type: 'textarea', rows: 2, placeholder: 'POST body (JSON)' },
  { key: 'timeout', label: '超时(秒)', type: 'number', placeholder: '30' },
];

function HTTPNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🌐"
      label="HTTP 请求"
      nodeType="http"
      fields={HTTP_FIELDS}
    />
  );
}

export default memo(HTTPNode);
