import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const JSON_FIELDS: NodeField[] = [
  { key: 'p4Path', label: 'P4 路径', placeholder: '//C7/.../file.json' },
  { key: 'jsonPath', label: 'JSON Path', placeholder: '$.data.items（可选）' },
];

function JsonNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="📋"
      label="JSON"
      fields={JSON_FIELDS}
    />
  );
}

export default memo(JsonNode);
