import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const REDIS_FIELDS: NodeField[] = [
  { key: 'command', label: '命令', type: 'select', options: [
    { label: 'GET', value: 'GET' },
    { label: 'SET', value: 'SET' },
    { label: 'HGET', value: 'HGET' },
    { label: 'HSET', value: 'HSET' },
    { label: 'DEL', value: 'DEL' },
    { label: 'KEYS', value: 'KEYS' },
  ], required: true },
  { key: 'key', label: 'Key', placeholder: 'Redis key', required: true },
  { key: 'field', label: 'Field', placeholder: 'Hash field (HGET/HSET)' },
  { key: 'value', label: 'Value', placeholder: '写入值 (SET/HSET)' },
];

function RedisNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🗄️"
      label="Redis"
      nodeType="redis"
      fields={REDIS_FIELDS}
    />
  );
}

export default memo(RedisNode);
