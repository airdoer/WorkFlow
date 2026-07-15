import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const MERGE_OBJECT_FIELDS: NodeField[] = [
  { key: 'overridesJson', label: '覆盖 JSON', type: 'textarea', required: false, placeholder: '{"3010603": 3}', description: '要覆盖/新增的键值对，JSON对象格式' },
];

function MergeObjectNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🔧"
      label="MergeObject"
      nodeType="mergeobject"
      fields={MERGE_OBJECT_FIELDS}
    />
  );
}

export default memo(MergeObjectNode);
