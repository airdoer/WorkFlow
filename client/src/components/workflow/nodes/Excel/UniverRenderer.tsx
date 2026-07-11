import React, { useRef, useEffect, useCallback, useMemo } from 'react';
import { createUniver, LocaleType, mergeLocales } from '@univerjs/presets';
import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core';
import UniverPresetSheetsCoreZhCN from '@univerjs/preset-sheets-core/locales/zh-CN';

import '@univerjs/preset-sheets-core/lib/index.css';

/* ─── Types ──────────────────────────────────────────────────────────────── */

/** Data format from backend Excel node output */
export interface ExcelTableData {
  columns: string[];
  rows: Record<string, any>[];
  sheetNames?: string[];
}

export interface UniverRendererProps {
  /** Structured table data (columns + rows) */
  data: ExcelTableData;
  /** ReactFlow node id — used to sync selection back to node data */
  nodeId?: string;
  /** Compact mode: smaller height, no toolbar (for node card in canvas) */
  compact?: boolean;
  /** Container height (default: compact=200, full=400) */
  height?: number;
  /** Callback when selection changes (selectedRows, selectedCols, selectedValues) */
  onSelectionChange?: (info: SelectionInfo) => void;
}

export interface SelectionInfo {
  selectedRows: number[];   // 1-based row indices
  selectedCols: string[];   // column names
  selectedValues: any;      // scalar (single cell) or 2D array (range)
}

/* ─── Data conversion: backend output → Univer IWorkbookData ─────────────── */

function toUniverWorkbookData(data: ExcelTableData, sheetName?: string): any {
  const { columns = [], rows = [] } = data;
  const sheetKey = sheetName || 'Sheet1';

  // Build cellData: row 0 = header, row 1..N = data rows
  const cellData: Record<number, Record<number, { v: string | number | null }>> = {};

  // Header row (row 0)
  cellData[0] = {};
  columns.forEach((col, ci) => {
    cellData[0][ci] = { v: col };
  });

  // Data rows (row 1..N)
  rows.forEach((row, ri) => {
    cellData[ri + 1] = {};
    columns.forEach((col, ci) => {
      const val = row[col];
      cellData[ri + 1][ci] = {
        v: val !== undefined && val !== null ? String(val) : '',
      };
    });
  });

  // Column count
  const colCount = columns.length;
  const rowCount = rows.length + 1; // +1 for header

  return {
    id: 'workbook-id',
    sheets: {
      [sheetKey]: {
        id: sheetKey,
        name: sheetKey,
        cellData,
        rowCount,
        colCount,
        // Default column widths
        defaultColumnWidth: 100,
        defaultRowHeight: 27,
        // Header row style (bold)
        rowData: {
          0: {
            hd: 0,
          },
        },
      },
    },
  };
}

// We need this variable outside the component because Univer defaultRowHeight
// depends on the compact prop but the data conversion is pure.
// We'll handle styles inside the component after creation.

/* ─── Selection extraction ────────────────────────────────────────────────── */

function extractSelectionFromUniver(
  univerAPI: any,
  columns: string[],
  rows: Record<string, any>[],
): SelectionInfo | null {
  try {
    const workbook = univerAPI.getActiveWorkbook();
    if (!workbook) return null;
    const sheet = workbook.getActiveSheet();
    if (!sheet) return null;
    const selection = sheet.getSelection();
    if (!selection) return null;

    const ranges = selection.getActiveRangeList?.() || [];
    if (!ranges || ranges.length === 0) return null;

    // Get the first range
    const range = ranges[0] || ranges;
    const startRow = range?.getRow?.() ?? range?.startRow ?? 0;
    const endRow = range?.getLastRow?.() ?? range?.endRow ?? 0;
    const startCol = range?.getColumn?.() ?? range?.startCol ?? 0;
    const endCol = range?.getLastColumn?.() ?? range?.endCol ?? 0;

    // Skip header row (row 0) — data starts from row 1
    const dataStartRow = Math.max(startRow - 1, 0); // skip header row
    const dataEndRow = Math.min(endRow - 1, rows.length - 1);
    const colStart = Math.max(startCol, 0);
    const colEnd = Math.min(endCol, columns.length - 1);

    if (dataStartRow > dataEndRow || colStart > colEnd) {
      return { selectedRows: [], selectedCols: [], selectedValues: [] };
    }

    const selectedRows: number[] = [];
    for (let r = dataStartRow; r <= dataEndRow; r++) {
      selectedRows.push(r + 1); // 1-based
    }

    const selectedCols = columns.slice(colStart, colEnd + 1);

    const selectedValues: any[][] = [];
    for (let r = dataStartRow; r <= dataEndRow; r++) {
      const rowVals: any[] = [];
      for (let c = colStart; c <= colEnd; c++) {
        rowVals.push(rows[r]?.[columns[c]] ?? null);
      }
      selectedValues.push(rowVals);
    }

    // Single cell → scalar; single value → unwrap
    let finalValues: any = selectedValues;
    if (selectedValues.length === 1 && selectedValues[0].length === 1) {
      finalValues = selectedValues[0][0];
    }

    return { selectedRows, selectedCols, selectedValues: finalValues };
  } catch (e) {
    // Selection API might not be available in all versions
    console.warn('[UniverRenderer] extractSelection failed:', e);
    return null;
  }
}

/* ─── The Component ──────────────────────────────────────────────────────── */

const UniverRenderer: React.FC<UniverRendererProps> = ({
  data,
  nodeId,
  compact = false,
  height,
  onSelectionChange,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const univerAPIRef = useRef<any>(null);
  const univerInstanceRef = useRef<any>(null);
  const columnsRef = useRef<string[]>(data.columns);
  const rowsRef = useRef<Record<string, any>[]>(data.rows);

  const containerHeight = height ?? (compact ? 200 : 400);

  // Keep refs in sync with props
  useEffect(() => {
    columnsRef.current = data.columns;
    rowsRef.current = data.rows;
  }, [data.columns, data.rows]);

  // Convert data to Univer format
  const workbookData = useMemo(() => {
    if (!data.columns.length && !data.rows.length) return null;
    return toUniverWorkbookData(data, data.sheetNames?.[0]);
  }, [data.columns, data.rows, data.sheetNames]);

  // Initialize Univer
  useEffect(() => {
    if (!containerRef.current || !workbookData) return;

    // Clean up previous instance
    if (univerInstanceRef.current) {
      try {
        univerInstanceRef.current.dispose();
      } catch (e) {
        // ignore
      }
      univerInstanceRef.current = null;
      univerAPIRef.current = null;
    }

    // Ensure container has a unique id
    const containerId = `univer-container-${nodeId || Math.random().toString(36).slice(2)}`;
    containerRef.current.id = containerId;

    const { univer, univerAPI } = createUniver({
      locale: LocaleType.ZH_CN,
      locales: {
        [LocaleType.ZH_CN]: mergeLocales(UniverPresetSheetsCoreZhCN),
      },
      presets: [
        UniverSheetsCorePreset({
          container: containerId,
        }),
      ],
    });

    univerInstanceRef.current = univer;
    univerAPIRef.current = univerAPI;

    // Create workbook with data
    univerAPI.createWorkbook(workbookData);

    // Listen for selection changes via command execution
    if (onSelectionChange) {
      try {
        const disposable = univerAPI.onCommandExecuted((command: any) => {
          // Selection change commands
          if (
            command?.id === 'sheet.command.set-selection' ||
            command?.id === 'sheet.operation.set-selection' ||
            command?.id?.includes?.('selection')
          ) {
            const sel = extractSelectionFromUniver(univerAPI, columnsRef.current, rowsRef.current);
            if (sel) {
              onSelectionChange(sel);
            }
          }
        });

        return () => {
          disposable?.dispose?.();
          try { univer.dispose(); } catch (e) { /* ignore */ }
          univerInstanceRef.current = null;
          univerAPIRef.current = null;
        };
      } catch (e) {
        // onCommandExecuted might not be available
        console.warn('[UniverRenderer] onCommandExecuted not available:', e);
      }
    }

    return () => {
      try { univer.dispose(); } catch (e) { /* ignore */ }
      univerInstanceRef.current = null;
      univerAPIRef.current = null;
    };
  }, [workbookData, nodeId, onSelectionChange]);

  if (!data.columns.length && !data.rows.length) {
    return <div style={{ color: '#999', fontSize: 12, padding: 8 }}>暂无 Excel 数据</div>;
  }

  return (
    <div className="nowheel nopan" style={{ height: containerHeight, position: 'relative' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      {/* Selection info badge */}
      {compact && onSelectionChange && (
        <div style={{
          position: 'absolute',
          bottom: 4,
          right: 4,
          fontSize: 10,
          color: '#1890ff',
          background: 'rgba(230,244,255,0.9)',
          padding: '1px 6px',
          borderRadius: 3,
          pointerEvents: 'none',
          zIndex: 10,
        }}>
          🖱 点击/框选单元格
        </div>
      )}
    </div>
  );
};

export default UniverRenderer;
