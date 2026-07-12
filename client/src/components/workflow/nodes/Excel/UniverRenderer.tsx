import React, { useRef, useEffect, useState, useCallback } from 'react';
import { createUniver, LocaleType, mergeLocales } from '@univerjs/presets';
import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core';
import UniverPresetSheetsCoreZhCN from '@univerjs/preset-sheets-core/locales/zh-CN';

import '@univerjs/preset-sheets-core/lib/index.css';

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface SheetData {
  name: string;
  columns: string[];
  rows: Record<string, any>[];
}

export interface ExcelTableData {
  columns: string[];
  rows: Record<string, any>[];
  sheetNames?: string[];
  /** Multi-sheet data: when available, each sheet has its own columns/rows */
  allSheets?: SheetData[];
}

export interface UniverRendererProps {
  data: ExcelTableData;
  nodeId?: string;
  /** Full mode: show Univer spreadsheet with toolbar. Compact mode: show simple HTML table with tabs */
  compact?: boolean;
  height?: number;
  onSelectionChange?: (info: SelectionInfo) => void;
}

export interface SelectionInfo {
  selectedRows: number[];
  selectedCols: string[];
  selectedValues: any;
}

/* ─── Data conversion ─────────────────────────────────────────────────────── */

function sheetToUniverSheet(sheet: SheetData): any {
  const { columns = [], rows = [] } = sheet;
  const cellData: Record<number, Record<number, any>> = {};

  // Header row (row 0) — bold
  cellData[0] = {};
  columns.forEach((col, ci) => {
    cellData[0][ci] = { v: col, s: { bl: 1 } };
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

  const colCount = columns.length;
  const rowCount = rows.length + 1;

  // Auto column widths
  const colData: Record<number, any> = {};
  columns.forEach((col, ci) => {
    let maxLen = col.length;
    rows.forEach((row) => {
      maxLen = Math.max(maxLen, String(row[col] ?? '').length);
    });
    colData[ci] = { w: Math.min(Math.max(maxLen * 9, 60), 300) };
  });

  // Sanitize sheet name for use as Univer sheet ID (alphanumeric + underscore)
  const sheetId = sheet.name.replace(/[^a-zA-Z0-9_]/g, '_');

  return {
    id: sheetId,
    name: sheet.name,
    cellData,
    rowCount,
    colCount,
    defaultColumnWidth: 100,
    defaultRowHeight: 27,
    colData,
    freeze: { startRow: 1, endRow: 1 },
  };
}

function toUniverWorkbookData(data: ExcelTableData): any {
  const allSheets = data.allSheets;

  if (allSheets && allSheets.length > 0) {
    // Multi-sheet mode: create workbook with all sheets
    const sheets: Record<string, any> = {};
    allSheets.forEach((s) => {
      const univerSheet = sheetToUniverSheet(s);
      sheets[univerSheet.id] = univerSheet;
    });

    return {
      id: `wb-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      sheets,
    };
  }

  // Single-sheet mode (backward compat)
  const sheetKey = data.sheetNames?.[0] || 'Sheet1';
  const singleSheet: SheetData = { name: sheetKey, columns: data.columns, rows: data.rows };
  const univerSheet = sheetToUniverSheet(singleSheet);

  return {
    id: `wb-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    sheets: { [univerSheet.id]: univerSheet },
  };
}

/* ─── Selection extraction ────────────────────────────────────────────────── */

function extractSelectionFromUniver(
  univerAPI: any,
  workbookId: string,
  allSheets: SheetData[],
): SelectionInfo | null {
  try {
    const workbook = univerAPI.getWorkbook(workbookId);
    if (!workbook) return null;
    const sheet = workbook.getActiveSheet();
    if (!sheet) return null;

    // Find the matching SheetData by sheet name
    const sheetName = sheet.getName?.() || sheet.getSheetId?.() || '';
    const sheetData = allSheets.find(s =>
      s.name === sheetName || s.name.replace(/[^a-zA-Z0-9_]/g, '_') === sheetName
    ) || allSheets[0];
    if (!sheetData) return null;

    const { columns, rows } = sheetData;

    const selection = sheet.getSelection();
    if (!selection) return null;

    const ranges = selection.getActiveRangeList?.() || [];
    if (!ranges || ranges.length === 0) return null;

    const range = Array.isArray(ranges) ? ranges[0] : ranges;
    const startRow = range?.getRow?.() ?? range?.startRow ?? 0;
    const endRow = range?.getLastRow?.() ?? range?.endRow ?? 0;
    const startCol = range?.getColumn?.() ?? range?.startCol ?? 0;
    const endCol = range?.getLastColumn?.() ?? range?.endCol ?? 0;

    const dataStartRow = Math.max(startRow - 1, 0);
    const dataEndRow = Math.min(endRow - 1, rows.length - 1);
    const colStart = Math.max(startCol, 0);
    const colEnd = Math.min(endCol, columns.length - 1);

    if (dataStartRow > dataEndRow || colStart > colEnd) {
      return { selectedRows: [], selectedCols: [], selectedValues: [] };
    }

    const selectedRows: number[] = [];
    for (let r = dataStartRow; r <= dataEndRow; r++) {
      selectedRows.push(r + 1);
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

    let finalValues: any = selectedValues;
    if (selectedValues.length === 1 && selectedValues[0].length === 1) {
      finalValues = selectedValues[0][0];
    }

    return { selectedRows, selectedCols, selectedValues: finalValues };
  } catch (e) {
    console.warn('[UniverRenderer] extractSelection failed:', e);
    return null;
  }
}

/* ─── Simple HTML Table (compact preview) with sheet tabs ─────────────────── */

const CompactTable: React.FC<{ data: ExcelTableData; height: number }> = React.memo(({ data, height }) => {
  const allSheets = data.allSheets;
  const [activeTab, setActiveTab] = useState(0);

  // Determine which sheet data to display
  const displaySheet: SheetData | null = allSheets && allSheets.length > 0
    ? allSheets[activeTab]
    : { name: data.sheetNames?.[0] || 'Sheet1', columns: data.columns, rows: data.rows };

  if (!displaySheet || !displaySheet.columns.length) {
    return <div style={{ color: '#999', fontSize: 12, padding: 8 }}>暂无 Excel 数据</div>;
  }

  const { columns = [], rows = [] } = displaySheet;
  const tabHeight = allSheets && allSheets.length > 1 ? 26 : 0;
  const tableHeight = height - tabHeight;
  const maxRows = Math.min(rows.length, Math.floor((tableHeight - 30) / 22));

  return (
    <div style={{ fontSize: 11, lineHeight: '20px', height, maxHeight: height, display: 'flex', flexDirection: 'column' }}>
      {/* Sheet tabs */}
      {allSheets && allSheets.length > 1 && (
        <div style={{
          display: 'flex', gap: 0, borderBottom: '1px solid #e8e8e8',
          flexShrink: 0, overflowX: 'auto', background: '#fafafa',
        }}>
          {allSheets.map((s, i) => (
            <button
              key={s.name}
              onClick={() => setActiveTab(i)}
              style={{
                border: 'none', background: i === activeTab ? '#fff' : 'transparent',
                padding: '3px 10px', fontSize: 10, cursor: 'pointer',
                borderBottom: i === activeTab ? '2px solid #1890ff' : '2px solid transparent',
                color: i === activeTab ? '#1890ff' : '#666',
                fontWeight: i === activeTab ? 600 : 400,
                whiteSpace: 'nowrap', minWidth: 0,
              }}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}

      {/* Table */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              {columns.map((col, i) => (
                <th key={i} style={{
                  background: '#fafafa',
                  borderBottom: '1px solid #e8e8e8',
                  padding: '2px 6px',
                  fontWeight: 600,
                  fontSize: 10,
                  whiteSpace: 'nowrap',
                  textAlign: 'left',
                  position: 'sticky',
                  top: 0,
                  zIndex: 1,
                }}>
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, maxRows).map((row, ri) => (
              <tr key={ri}>
                {columns.map((col, ci) => (
                  <td key={ci} style={{
                    borderBottom: '1px solid #f0f0f0',
                    padding: '1px 6px',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    maxWidth: 150,
                  }}>
                    {row[col] !== undefined && row[col] !== null ? String(row[col]) : ''}
                  </td>
                ))}
              </tr>
            ))}
            {rows.length > maxRows && (
              <tr>
                <td colSpan={columns.length} style={{ padding: '2px 6px', color: '#999', fontSize: 10, textAlign: 'center' }}>
                  ... 还有 {rows.length - maxRows} 行
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
});

/* ─── The Component ──────────────────────────────────────────────────────── */

let _univerContainerCounter = 0;

const UniverRenderer: React.FC<UniverRendererProps> = ({
  data,
  nodeId,
  compact = false,
  height,
  onSelectionChange,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const workbookIdRef = useRef<string | null>(null);
  const univerAPIRef = useRef<any>(null);
  const univerRef = useRef<any>(null);
  const allSheetsRef = useRef<SheetData[]>(
    data.allSheets || [{ name: data.sheetNames?.[0] || 'Sheet1', columns: data.columns, rows: data.rows }]
  );
  const onSelectionChangeRef = useRef(onSelectionChange);
  const selDebounceRef = useRef<any>(null);
  const isDisposedRef = useRef(false);

  const containerIdRef = useRef<string>(
    `univer-full-${nodeId || (++_univerContainerCounter)}`
  );

  const containerHeight = height ?? (compact ? 200 : 400);

  // Keep refs in sync
  useEffect(() => {
    allSheetsRef.current = data.allSheets || [
      { name: data.sheetNames?.[0] || 'Sheet1', columns: data.columns, rows: data.rows },
    ];
  }, [data.allSheets, data.columns, data.rows, data.sheetNames]);

  useEffect(() => {
    onSelectionChangeRef.current = onSelectionChange;
  }, [onSelectionChange]);

  // ─── Full Univer mode (non-compact): init with delay ──
  useEffect(() => {
    if (compact) return;

    const container = containerRef.current;
    if (!container) return;

    isDisposedRef.current = false;
    container.id = containerIdRef.current;

    // Delay init to ensure container has actual dimensions
    const initTimer = setTimeout(() => {
      if (isDisposedRef.current) return;

      const rect = container.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) {
        console.warn('[UniverRenderer] Container has zero dimensions, skipping init');
        return;
      }

      // Create a fresh Univer instance for this container
      const { univer, univerAPI } = createUniver({
        locale: LocaleType.ZH_CN,
        locales: {
          [LocaleType.ZH_CN]: mergeLocales(UniverPresetSheetsCoreZhCN),
        },
        presets: [
          UniverSheetsCorePreset({
            container: containerIdRef.current,
          }),
        ],
      });

      univerRef.current = univer;
      univerAPIRef.current = univerAPI;

      // Create workbook with multi-sheet data
      const wbData = toUniverWorkbookData(data);
      if (wbData) {
        try {
          const wb = univerAPI.createWorkbook(wbData);
          workbookIdRef.current = wb?.getUnitId?.() ?? null;
        } catch (e) {
          console.warn('[UniverRenderer] createWorkbook failed:', e);
        }
      }

      // Listen for selection changes
      if (onSelectionChange) {
        try {
          const disposable = univerAPI.onCommandExecuted((command: any) => {
            if (isDisposedRef.current || !workbookIdRef.current) return;
            if (
              command?.id === 'sheet.command.set-selection' ||
              command?.id === 'sheet.operation.set-selection' ||
              command?.id?.includes?.('selection')
            ) {
              if (selDebounceRef.current) clearTimeout(selDebounceRef.current);
              selDebounceRef.current = setTimeout(() => {
                if (isDisposedRef.current || !workbookIdRef.current) return;
                const sel = extractSelectionFromUniver(
                  univerAPI, workbookIdRef.current,
                  allSheetsRef.current,
                );
                if (sel && onSelectionChangeRef.current) {
                  onSelectionChangeRef.current(sel);
                }
              }, 150);
            }
          });
          (univerRef.current as any)._selDisposable = disposable;
        } catch (e) {
          console.warn('[UniverRenderer] onCommandExecuted setup failed:', e);
        }
      }
    }, 200);

    return () => {
      isDisposedRef.current = true;
      clearTimeout(initTimer);
      if (selDebounceRef.current) clearTimeout(selDebounceRef.current);

      const univerToDispose = univerRef.current;
      const containerId = containerIdRef.current;
      requestAnimationFrame(() => {
        try {
          const d = (univerToDispose as any)?._selDisposable;
          d?.dispose?.();
        } catch (e) { /* ignore */ }
        try {
          if (univerToDispose) univerToDispose.dispose();
        } catch (e) { /* ignore */ }
        const el = document.getElementById(containerId);
        if (el) el.innerHTML = '';
      });

      univerRef.current = null;
      univerAPIRef.current = null;
      workbookIdRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compact]);

  const hasAnyData = data.allSheets?.some(s => s.columns.length > 0 || s.rows.length > 0)
    || (data.columns.length > 0 || data.rows.length > 0);

  if (!hasAnyData) {
    return <div style={{ color: '#999', fontSize: 12, padding: 8 }}>暂无 Excel 数据</div>;
  }

  // Compact mode: render HTML table with sheet tabs
  if (compact) {
    return <CompactTable data={data} height={containerHeight} />;
  }

  // Full mode: render Univer container
  return (
    <div className="nowheel nopan" style={{ height: containerHeight, position: 'relative' }}>
      <div
        ref={containerRef}
        id={containerIdRef.current}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
};

export default React.memo(UniverRenderer);
