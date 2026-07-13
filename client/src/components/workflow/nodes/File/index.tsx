import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const FILE_FIELDS: NodeField[] = [
  { key: 'path', label: '文件路径', placeholder: '/path/to/file.txt', required: true },
  { key: 'encoding', label: '编码', placeholder: 'utf-8' },
];

function FileNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="📄"
      label="文件"
      nodeType="file"
      fields={FILE_FIELDS}
    />
  );
}

export default memo(FileNode);
