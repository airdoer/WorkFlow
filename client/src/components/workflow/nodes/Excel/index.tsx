import React, { memo, useMemo, useCallback, useRef } from 'react';
import { NodeProps, useReactFlow } from 'reactflow';
import { useWorkflowContext } from '../../WorkflowContext';
import BaseNode, { type NodeField } from '../BaseNode';
import UniverRenderer, { type ExcelTableData, type SheetData } from './UniverRenderer';

/* ─── ExcelNode ─────────────────────────────────────────────────────────── */
function ExcelNode({ data, id, selected }: NodeProps) {
  const nodeData = data as Record<string, unknown>;
  const { getRunOutput } = useWorkflowContext();
  const runOutput = getRunOutput(id);
  const { setNodes } = useReactFlow();

  // helpers
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

  // Build render data — only pass allSheets when no specific sheetName is selected
  const cols = runOutput?.columns as string[] | undefined;
  const rows = runOutput?.rows as Record<string, any>[] | undefined;
  const sheetNames = runOutput?.sheetNames as string[] | undefined;
  const allSheets = runOutput?.allSheets as SheetData[] | undefined;
  const hasSheetName = !!(nodeData.sheetName as string); // 是否选了指定 sheet

  const excelData: ExcelTableData | null = useMemo(() => {
    if (!cols || !rows) return null;
    // 选了 sheetName → 只渲染该 sheet（不传 allSheets）；未选 → 显示所有 sheet tabs
    return { columns: cols, rows, sheetNames, activeSheetName: hasSheetName ? (nodeData.sheetName as string) : undefined, allSheets: hasSheetName ? undefined : allSheets };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    cols?.join(','),
    rows?.length,
    sheetNames?.join(','),
    allSheets?.length,
    hasSheetName,
  ]);

  // NOTE: No onSelectionChange in compact node card — this prevents
  // infinite re-render loops when setNodes triggers ReactFlow re-render.
  // Selection changes are only captured in the NodeDetailModal (fullscreen).

  return (
    <BaseNode
      data={nodeData}
      id={id}
      selected={!!selected}
      icon="📊"
      label="Excel"
      nodeType="excel"
      fields={EXCEL_FIELDS}
    />
  );
}

export default memo(ExcelNode);
