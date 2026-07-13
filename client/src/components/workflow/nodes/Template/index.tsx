import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const TEMPLATE_FIELDS: NodeField[] = [
  { key: 'template', label: '模板', type: 'textarea', rows: 3, placeholder: '物品{{name}}，数量{{count}}', required: true },
];

function TemplateNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="📝"
      label="模板"
      nodeType="template"
      fields={TEMPLATE_FIELDS}
    />
  );
}

export default memo(TemplateNode);
