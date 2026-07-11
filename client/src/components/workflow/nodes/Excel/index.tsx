import React, { memo, useMemo, useState, useCallback, useEffect } from 'react';
import { NodeProps, useReactFlow } from 'reactflow';
import { Table, Input } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import BaseNode, { type NodeField } from '../BaseNode';

/* ─── 表格渲染器（带单元格选中 + 搜索） ────────────────────────────────── */
interface ExcelTableData {
  columns: string[];
  rows: Record<string, any>[];
  sheetNames?: string[];
}

interface ExcelRendererProps {
  data: ExcelTableData;
  nodeId: string;
  compact?: boolean;
}

function ExcelRenderer({ data, nodeId, compact = false }: ExcelRendererProps) {
  const { columns = [], rows = [], sheetNames = [] } = data;
  const { setNodes } = useReactFlow();

  const [search, setSearch] = useState('');
  const [selectedCell, setSelectedCell] = useState<{ row: number; col: string } | null>(null);
  const [selectionStart, setSelectionStart] = useState<{ row: number; col: string } | null>(null);
  const [selectionEnd, setSelectionEnd] = useState<{ row: number; col: string } | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  // 过滤行
  const filteredRows = useMemo(() => {
    if (!search.trim()) return rows.map((r, i) => ({ ...r, _rowIdx: i }));
    const q = search.toLowerCase();
    return rows
      .map((r, i) => ({ ...r, _rowIdx: i }))
      .filter((r) => columns.some((c) => String(r[c] ?? '').toLowerCase().includes(q)));
  }, [rows, columns, search]);

  // 计算选中区域（矩形）
  const selectedRange = useMemo(() => {
    if (!selectionStart || !selectionEnd) return null;
    const colIndexOf = (col: string) => columns.indexOf(col);
    const startColIdx = colIndexOf(selectionStart.col);
    const endColIdx   = colIndexOf(selectionEnd.col);
    const minCol = Math.min(startColIdx, endColIdx);
    const maxCol = Math.max(startColIdx, endColIdx);
    const minRow = Math.min(selectionStart.row, selectionEnd.row);
    const maxRow = Math.max(selectionStart.row, selectionEnd.row);
    return { minCol, maxCol, minRow, maxRow };
  }, [selectionStart, selectionEnd, columns]);

  const isCellSelected = useCallback((rowIdx: number, col: string) => {
    if (!selectedRange) return false;
    const colIdx = columns.indexOf(col);
    return (
      rowIdx >= selectedRange.minRow && rowIdx <= selectedRange.maxRow &&
      colIdx >= selectedRange.minCol && colIdx <= selectedRange.maxCol
    );
  }, [selectedRange, columns]);

  // 鼠标事件处理
  const handleCellMouseDown = useCallback((rowIdx: number, col: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectionStart({ row: rowIdx, col });
    setSelectionEnd({ row: rowIdx, col });
    setSelectedCell({ row: rowIdx, col });
    setIsDragging(true);
  }, []);

  const handleCellMouseEnter = useCallback((rowIdx: number, col: string) => {
    if (!isDragging) return;
    setSelectionEnd({ row: rowIdx, col });
  }, [isDragging]);

  const handleMouseUp = useCallback(() => {
    if (!isDragging) return;
    setIsDragging(false);
    // 同步选中结果到 node data
    if (!selectedRange) return;
    const selRows: number[] = [];
    for (let r = selectedRange.minRow; r <= selectedRange.maxRow; r++) selRows.push(r + 1); // 1-based
    const selCols = columns.slice(selectedRange.minCol, selectedRange.maxCol + 1);
    const selValues = rows
      .slice(selectedRange.minRow, selectedRange.maxRow + 1)
      .map((row) => selCols.map((c) => row[c] ?? null));
    const finalValues = selValues.length === 1 && selValues[0].length === 1 ? selValues[0][0] : selValues;

    setNodes((nds) =>
      nds.map((n) =>
        n.id === nodeId
          ? { ...n, data: { ...n.data, _selectedRows: selRows, _selectedCols: selCols, _selectedValues: finalValues } }
          : n,
      ),
    );
  }, [isDragging, selectedRange, rows, columns, nodeId, setNodes]);

  useEffect(() => {
    window.addEventListener('mouseup', handleMouseUp);
    return () => window.removeEventListener('mouseup', handleMouseUp);
  }, [handleMouseUp]);

  const antdColumns = useMemo(() => {
    const rowNumCol = {
      title: '#',
      dataIndex: '_rowIdx',
      key: '_rowIdx',
      width: 36,
      fixed: 'left' as const,
      render: (v: number) => (
        <span style={{ fontSize: 10, color: '#8c8c8c' }}>{v + 1}</span>
      ),
    };

    const dataCols = columns.map((col) => ({
      title: (
        <span style={{ fontSize: 11, whiteSpace: 'nowrap' }}>{col}</span>
      ),
      dataIndex: col,
      key: col,
      ellipsis: true,
      width: 120,
      render: (val: any, record: any) => {
        const rowIdx = record._rowIdx as number;
        const sel = isCellSelected(rowIdx, col);
        return (
          <div
            onMouseDown={(e) => handleCellMouseDown(rowIdx, col, e)}
            onMouseEnter={() => handleCellMouseEnter(rowIdx, col)}
            style={{
              fontSize: compact ? 10 : 11,
              cursor: 'cell',
              padding: '1px 2px',
              userSelect: 'none',
              background: sel ? 'rgba(24,144,255,0.12)' : 'transparent',
              border: sel ? '1px solid rgba(24,144,255,0.4)' : '1px solid transparent',
              borderRadius: 2,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: '100%',
            }}
            title={String(val ?? '')}
          >
            {String(val ?? '')}
          </div>
        );
      },
    }));

    return [rowNumCol, ...dataCols];
  }, [columns, isCellSelected, handleCellMouseDown, handleCellMouseEnter, compact]);

  if (!columns.length) {
    return <div style={{ color: '#999', fontSize: 12, padding: 8 }}>暂无 Excel 数据</div>;
  }

  return (
    <div className="nowheel nopan">
      {/* 搜索框 */}
      <div style={{
        padding: '4px 6px', background: '#f5f5f5',
        borderBottom: '1px solid #e8e8e8', borderTop: '1px solid #e8e8e8',
      }}>
        <Input
          prefix={<SearchOutlined style={{ color: '#bfbfbf', fontSize: 11 }} />}
          placeholder="搜索..."
          size="small"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          allowClear
          style={{ fontSize: 11, height: 22 }}
        />
      </div>

      {/* 表格 */}
      <div style={{ border: '1px solid #e8e8e8', borderTop: 'none', borderRadius: '0 0 4px 4px', overflow: 'hidden' }}>
        <Table
          columns={antdColumns}
          dataSource={filteredRows}
          rowKey="_rowIdx"
          pagination={false}
          size="small"
          scroll={{ x: 'max-content', y: compact ? 150 : 280 }}
          style={{ fontSize: 11 }}
          locale={{ emptyText: '(空)' }}
          rowClassName={(_, idx) => idx % 2 === 0 ? '' : 'ant-table-row-striped'}
        />
      </div>

      {/* 选中信息提示 */}
      {selectedRange && (
        <div style={{ fontSize: 10, color: '#1890ff', padding: '2px 6px', background: '#e6f4ff', borderTop: '1px solid #bae0ff' }}>
          已选 {selectedRange.maxRow - selectedRange.minRow + 1} 行 × {selectedRange.maxCol - selectedRange.minCol + 1} 列
        </div>
      )}
    </div>
  );
}

/* ─── ExcelNode ─────────────────────────────────────────────────────────── */
function ExcelNode({ data, id, selected }: NodeProps) {
  const nodeData = data as Record<string, unknown>;
  const runOutput = nodeData._runOutput as any;

  // 动态 options：运行后才有列/行信息
  const rowOptions = useMemo(() => {
    const rows = runOutput?.rows as Record<string, any>[] | undefined;
    const cols = runOutput?.columns as string[] | undefined;
    if (!rows || !cols || cols.length === 0) return [];
    const firstCol = cols[0]; // 第一列作为行标识
    return rows.map((row, i) => {
      const label = String(row[firstCol] ?? `第 ${i + 1} 行`);
      return { label, value: label }; // value 也用第一列值，便于后端匹配
    });
  }, [runOutput]);

  const colOptions = useMemo(() => {
    if (!runOutput?.columns) return [];
    return (runOutput.columns as string[]).map((c: string) => ({ label: c, value: c }));
  }, [runOutput]);

  const sheetOptions = useMemo(() => {
    const names = runOutput?.sheetNames as string[] | undefined;
    if (!names || names.length === 0) return [];
    return names.map((s: string) => ({ label: s, value: s }));
  }, [runOutput]);

  const EXCEL_FIELDS: NodeField[] = [
    {
      key: 'sheetName',
      label: 'Sheet 名',
      type: 'select',
      options: sheetOptions,
      placeholder: '选择工作表（有连线时由连线提供）',
      linkedPortKey: 'sheetName',
    },
    {
      key: 'filterRows',
      label: '筛选行',
      type: 'multiselect',
      options: rowOptions,
      placeholder: '选择行（空则显示全部）',
    },
    {
      key: 'filterColumns',
      label: '筛选列',
      type: 'multiselect',
      options: colOptions,
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

  // 自定义内容区（表格显示）
  const tableContent = excelData ? (
    <ExcelRenderer data={excelData} nodeId={id} compact />
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
