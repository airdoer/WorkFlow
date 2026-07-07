import React, { memo, useEffect, useState } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const EXCEL_FIELDS: NodeField[] = [
  { key: 'sheet', label: '工作表', placeholder: '工作表名（可选）' },
  { key: 'rowFilter', label: '行筛选', type: 'multiselect', placeholder: '选择行号' },
  { key: 'columnFilter', label: '列筛选', type: 'multiselect', placeholder: '选择列' },
];

function ExcelNode({ data, id, selected }: NodeProps) {
  // Row/Column filter options are dynamically populated after run
  const [rowOptions, setRowOptions] = useState<{ label: string; value: string }[]>([]);
  const [colOptions, setColOptions] = useState<{ label: string; value: string }[]>([]);

  const runOutput = data._runOutput as any;
  useEffect(() => {
    if (runOutput && runOutput.columns) {
      setColOptions(runOutput.columns.map((c: string) => ({ label: c, value: c })));
      const rowCount = runOutput.rows?.length || 0;
      setRowOptions(
        Array.from({ length: rowCount }, (_, i) => ({
          label: `第 ${i + 1} 行`,
          value: String(i + 1),
        })),
      );
    }
  }, [runOutput]);

  // Inject dynamic options into fields
  const fieldsWithDynamic: NodeField[] = EXCEL_FIELDS.map((f) => {
    if (f.key === 'rowFilter') return { ...f, options: rowOptions };
    if (f.key === 'columnFilter') return { ...f, options: colOptions };
    return f;
  });

  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="📊"
      label="Excel"
      nodeType="excel"
      fields={fieldsWithDynamic}
    />
  );
}

export default memo(ExcelNode);
