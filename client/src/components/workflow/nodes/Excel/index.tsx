import React, { memo, useMemo, useCallback } from 'react';
import { NodeProps, useReactFlow } from 'reactflow';
import BaseNode, { type NodeField } from '../BaseNode';
import UniverRenderer, { type ExcelTableData, type SelectionInfo } from './UniverRenderer';

/* ─── ExcelNode ─────────────────────────────────────────────────────────── */
function ExcelNode({ data, id, selected }: NodeProps) {
  const nodeData = data as Record<string, unknown>;
  const runOutput = nodeData._runOutput as any;
  const { setNodes } = useReactFlow();

  // helpers：从 _runOutput 实时计算 options，避免 useMemo 缓存旧值
  const makeRowOptions = (d: Record<string, any>) => {
    const ro = d._runOutput as any;
    const rows = (ro?.allRows ?? ro?.rows) as Record<string, any>[] | undefined;
    const cols = (ro?.allColumns ?? ro?.columns) as string[] | undefined;
    if (!rows || !cols || cols.length === 0) return [];
    const firstCol = cols[0];
    return rows.map((row: Record<string, any>, i: number) => {
      const label = String(row[firstCol] ?? `第 ${i + 1} 行`);
      return { label, value: label };
    });
  };

  const makeColOptions = (d: Record<string, any>) => {
    const ro = d._runOutput as any;
    const cols = (ro?.allColumns ?? ro?.columns) as string[] | undefined;
    if (!cols) return [];
    return cols.map((c: string) => ({ label: c, value: c }));
  };

  const makeSheetOptions = (d: Record<string, any>) => {
    const ro = d._runOutput as any;
    const names = ro?.sheetNames as string[] | undefined;
    if (!names || names.length === 0) return [];
    return names.map((s: string) => ({ label: s, value: s }));
  };

  const EXCEL_FIELDS: NodeField[] = [
    {
      key: 'sheetName',
      label: 'Sheet 名',
      type: 'select',
      optionsFn: makeSheetOptions,
      placeholder: '选择工作表（有连线时由连线提供）',
      linkedPortKey: 'sheetName',
    },
    {
      key: 'filterRows',
      label: '筛选行',
      type: 'multiselect',
      optionsFn: makeRowOptions,
      placeholder: '选择行（空则显示全部）',
    },
    {
      key: 'filterColumns',
      label: '筛选列',
      type: 'multiselect',
      optionsFn: makeColOptions,
      placeholder: '选择列（空则显示全部）',
    },
  ];

  // 构建渲染数据
  const excelData: ExcelTableData | null = useMemo(() => {
    if (!runOutput) return null;
    const cols = runOutput.columns as string[] | undefined;
    const rows = runOutput.rows as Record<string, any>[] | undefined;
    if (!cols || !rows) return null;
    return { columns: cols, rows, sheetNames: runOutput.sheetNames };
  }, [runOutput]);

  // 选中事件回调：同步到 node data
  const handleSelectionChange = useCallback((info: SelectionInfo) => {
    setNodes((nds) =>
      nds.map((n) =>
        n.id === id
          ? {
              ...n,
              data: {
                ...n.data,
                _selectedRows: info.selectedRows,
                _selectedCols: info.selectedCols,
                _selectedValues: info.selectedValues,
              },
            }
          : n,
      ),
    );
  }, [id, setNodes]);

  // 自定义内容区（Univer 表格显示）
  const tableContent = excelData ? (
    <UniverRenderer
      data={excelData}
      nodeId={id}
      compact
      height={200}
      onSelectionChange={handleSelectionChange}
    />
  ) : null;

  return (
    <BaseNode
      data={nodeData}
      id={id}
      selected={!!selected}
      icon="📊"
      label="Excel"
      nodeType="excel"
      fields={EXCEL_FIELDS}
      extraContentAfterFields={tableContent}
    />
  );
}

export default memo(ExcelNode);
