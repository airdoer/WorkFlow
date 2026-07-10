import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const P4FILE_FIELDS: NodeField[] = [
  {
    key: 'p4Path',
    label: 'P4 路径',
    placeholder: '//C7/.../file.xlsx（可由连线提供）',
    required: true,
    linkedPortKey: 'p4Path',
  },
];

function P4FileNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="📁"
      label="P4 文件"
      nodeType="p4file"
      fields={P4FILE_FIELDS}
    />
  );
}

export default memo(P4FileNode);
