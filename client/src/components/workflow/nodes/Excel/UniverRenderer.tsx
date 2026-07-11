import React, { useRef, useEffect } from 'react';
import { createUniver, LocaleType, mergeLocales } from '@univerjs/presets';
import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core';
import UniverPresetSheetsCoreZhCN from '@univerjs/preset-sheets-core/locales/zh-CN';

import '@univerjs/preset-sheets-core/lib/index.css';

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface ExcelTableData {
  columns: string[];
  rows: Record<string, any>[];
  sheetNames?: string[];
}

export interface UniverRendererProps {
  data: ExcelTableData;
  nodeId?: string;
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

function toUniverWorkbookData(data: ExcelTableData, sheetName?: string): any {
  const { columns = [], rows = [] } = data;
  const sheetKey = sheetName || 'Sheet1';

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

  return {
    id: 'workbook-id',
    sheets: {
      [sheetKey]: {
        id: sheetKey,
        name: sheetKey,
        cellData,
        rowCount,
        colCount,
        defaultColumnWidth: 100,
        defaultRowHeight: 27,
        colData,
        freeze: { startRow: 1, endRow: 1 },
      },
    },
  };
}

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

/* ─── Compact mode CSS ────────────────────────────────────────────────────── */

// Inject a global <style> tag once to hide Univer chrome in compact containers
let _compactStyleInjected = false;
function injectCompactStyle() {
  if (_compactStyleInjected) return;
  _compactStyleInjected = true;
  const style = document.createElement('style');
  style.id = 'univer-compact-override';
  style.textContent = `
    .univer-compact header {
      display: none !important;
      height: 0 !important;
      min-height: 0 !important;
      overflow: hidden !important;
    }
    .univer-compact footer {
      display: none !important;
      height: 0 !important;
      min-height: 0 !important;
      overflow: hidden !important;
    }
  `;
  document.head.appendChild(style);
}

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
  const univerAPIRef = useRef<any>(null);
  const univerInstanceRef = useRef<any>(null);
  const columnsRef = useRef<string[]>(data.columns);
  const rowsRef = useRef<Record<string, any>[]>(data.rows);
  const onSelectionChangeRef = useRef(onSelectionChange);
  const isInitializedRef = useRef(false);
  const lastDataKeyRef = useRef<string>('');
  const selDebounceRef = useRef<any>(null);

  const containerIdRef = useRef<string>(
    `univer-c-${nodeId || (++_univerContainerCounter)}`
  );

  const containerHeight = height ?? (compact ? 200 : 400);

  // Keep refs in sync
  useEffect(() => {
    columnsRef.current = data.columns;
    rowsRef.current = data.rows;
  }, [data.columns, data.rows]);

  useEffect(() => {
    onSelectionChangeRef.current = onSelectionChange;
  }, [onSelectionChange]);

  // Stable key for data comparison
  const dataKey = `${data.columns.join(',')}|${data.rows.length}|${data.sheetNames?.join(',')}`;
  const workbookData = data.columns.length > 0
    ? toUniverWorkbookData(data, data.sheetNames?.[0])
    : null;

  // Inject compact CSS once
  useEffect(() => {
    if (compact) injectCompactStyle();
  }, [compact]);

  // ─── Init Univer ONCE on mount ────────────────────────────────────────
  useEffect(() => {
    const container = containerRef.current;
    if (!container || isInitializedRef.current) return;

    isInitializedRef.current = true;
    container.id = containerIdRef.current;

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

    univerInstanceRef.current = univer;
    univerAPIRef.current = univerAPI;

    // Create empty workbook first — real data will be loaded in next effect
    univerAPI.createWorkbook({});

    // Selection listener with debounce
    try {
      const disposable = univerAPI.onCommandExecuted((command: any) => {
        if (
          command?.id === 'sheet.command.set-selection' ||
          command?.id === 'sheet.operation.set-selection' ||
          command?.id?.includes?.('selection')
        ) {
          if (selDebounceRef.current) clearTimeout(selDebounceRef.current);
          selDebounceRef.current = setTimeout(() => {
            const sel = extractSelectionFromUniver(univerAPI, columnsRef.current, rowsRef.current);
            if (sel && onSelectionChangeRef.current) {
              onSelectionChangeRef.current(sel);
            }
          }, 100);
        }
      });
      (univerInstanceRef.current as any)._selDisposable = disposable;
    } catch (e) {
      console.warn('[UniverRenderer] onCommandExecuted not available:', e);
    }

    return () => {
      if (selDebounceRef.current) clearTimeout(selDebounceRef.current);
      try {
        const d = (univerInstanceRef.current as any)?._selDisposable;
        d?.dispose?.();
      } catch (e) { /* ignore */ }
      try { univer.dispose(); } catch (e) { /* ignore */ }
      univerInstanceRef.current = null;
      univerAPIRef.current = null;
      isInitializedRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Mount-only

  // ─── Update workbook when data actually changes ───────────────────────
  useEffect(() => {
    const api = univerAPIRef.current;
    if (!api || !workbookData) return;

    if (dataKey === lastDataKeyRef.current) return;
    lastDataKeyRef.current = dataKey;

    try {
      const workbook = api.getActiveWorkbook();
      if (workbook) {
        const unitId = workbook.getUnitId?.();
        if (unitId) {
          try { api.disposeWorkbook(unitId); } catch (e) { /* ignore */ }
        }
      }
      api.createWorkbook(workbookData);
    } catch (e) {
      console.warn('[UniverRenderer] Failed to update workbook:', e);
    }
  }, [dataKey, workbookData]);

  if (!data.columns.length && !data.rows.length) {
    return <div style={{ color: '#999', fontSize: 12, padding: 8 }}>暂无 Excel 数据</div>;
  }

  return (
    <div className={`nowheel nopan ${compact ? 'univer-compact' : ''}`} style={{ height: containerHeight, position: 'relative' }}>
      <div
        ref={containerRef}
        id={containerIdRef.current}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
};

export default React.memo(UniverRenderer);
