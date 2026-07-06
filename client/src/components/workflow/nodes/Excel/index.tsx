import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const EXCEL_FIELDS: NodeField[] = [
  { key: 'p4Path', label: 'P4 路径', placeholder: '//C7/.../file.xlsx' },
  { key: 'sheet', label: '工作表', placeholder: '工作表名（可选）' },
];

function ExcelNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="📊"
      label="Excel"
      fields={EXCEL_FIELDS}
    />
  );
}

export default memo(ExcelNode);
