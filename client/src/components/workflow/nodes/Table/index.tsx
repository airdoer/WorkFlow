/**
 * TableNode
 * - 接受上游数据（tableInput 端口：string / json-data / any）
 * - 解析为结构化表格：数组 → 单表，字典 → 多表
 * - 在节点卡片中直接渲染 antd Table，支持搜索筛选
 */

import React, { memo, useCallback, useState, useMemo } from 'react';
import { NodeProps, Handle, Position, useReactFlow } from 'reactflow';
import { Table, Input } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import {
  PlayCircleOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExpandOutlined,
} from '@ant-design/icons';
import { FlowApi } from '../../services/FlowApi';
import { getNodePorts } from '../../PortTypes';
import { useWorkflowContext } from '../../WorkflowContext';
import NodeDetailModal from '../NodeDetailModal';
import { NodeField, SeqBadge } from '../BaseNode';

type RunStatus = 'idle' | 'running' | 'success' | 'error';

const STATUS_CONFIG = {
  idle:    { color: '#8c8c8c', bg: '#f5f5f5', icon: PlayCircleOutlined,  title: '运行节点' },
  running: { color: '#1890ff', bg: '#e6f7ff', icon: LoadingOutlined,      title: '运行中...' },
  success: { color: '#52c41a', bg: '#f6ffed', icon: CheckCircleOutlined,  title: '运行成功' },
  error:   { color: '#ff4d4f', bg: '#fff2f0', icon: CloseCircleOutlined,  title: '运行失败' },
};

const PORT_COLORS: Record<string, string> = {
  'any':        '#8c8c8c',
  'table-data': '#13c2c2',
  'string':     '#52c41a',
  'json-data':  '#2f54eb',
};

/* ─── Mini table renderer ───────────────────────────────────────────────── */
interface TableData {
  title?: string | null;
  columns: string[];
  rows: string[][];
}

/** Convert columns + rows to antd-compatible dataSource & columns */
function buildAntdTable(table: TableData, searchText: string, maxRows: number) {
  const { columns, rows } = table;

  const filtered = searchText.trim()
    ? rows.filter((row) => row.some((cell) => String(cell ?? '').toLowerCase().includes(searchText.toLowerCase())))
    : rows;

  const visibleRows = filtered.slice(0, maxRows);

  const antColumns = columns.map((col, colIdx) => ({
    title: col,
    dataIndex: `col_${colIdx}`,
    key: `col_${colIdx}`,
    ellipsis: true,
    width: 120,
    render: (val: string) => (
      <span title={val} style={{ fontSize: 11 }}>{val}</span>
    ),
  }));

  const dataSource = visibleRows.map((row, rowIdx) => {
    const obj: Record<string, string> = { key: String(rowIdx) };
    columns.forEach((_, colIdx) => {
      obj[`col_${colIdx}`] = row[colIdx] ?? '';
    });
    return obj;
  });

  return { antColumns, dataSource, filteredCount: filtered.length, totalCount: rows.length };
}

function MiniTable({ table, maxRows = 50, compact = false }: { table: TableData; maxRows?: number; compact?: boolean }) {
  const [search, setSearch] = useState('');
  const { title } = table;

  const { antColumns, dataSource, filteredCount, totalCount } = useMemo(
    () => buildAntdTable(table, search, maxRows),
    [table, search, maxRows],
  );

  const truncated = filteredCount > maxRows;

  return (
    <div style={{ marginBottom: compact ? 6 : 12 }} className="nowheel nopan">
      {/* Title bar */}
      {title && (
        <div style={{
          fontSize: 11, fontWeight: 600, color: '#fff',
          padding: '3px 8px', background: '#1890ff',
          borderRadius: '4px 4px 0 0', letterSpacing: 0.3,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span>{title}</span>
          <span style={{ fontWeight: 400, opacity: 0.85, fontSize: 10 }}>{totalCount} 行</span>
        </div>
      )}

      {/* Search input */}
      <div style={{
        background: '#f5f5f5',
        padding: '4px 6px',
        borderBottom: '1px solid #e8e8e8',
        borderTop: title ? undefined : '1px solid #e8e8e8',
        borderLeft: '1px solid #e8e8e8',
        borderRight: '1px solid #e8e8e8',
        borderRadius: title ? undefined : '4px 4px 0 0',
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

      {/* Antd Table */}
      <div style={{
        border: '1px solid #e8e8e8',
        borderTop: 'none',
        borderRadius: '0 0 4px 4px',
        overflow: 'hidden',
      }}>
        <Table
          columns={antColumns}
          dataSource={dataSource}
          pagination={false}
          size="small"
          scroll={{ x: 'max-content', y: compact ? 150 : 240 }}
          style={{ fontSize: 11 }}
          locale={{ emptyText: '(空)' }}
          rowClassName={(_, idx) => idx % 2 === 0 ? '' : 'ant-table-row-striped'}
        />
        {truncated && (
          <div style={{
            fontSize: 10, color: '#8c8c8c', padding: '3px 8px',
            borderTop: '1px solid #f0f0f0', background: '#fafafa',
          }}>
            已过滤 {filteredCount} 条，显示前 {maxRows} 行（共 {totalCount} 行）
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── TableNode ─────────────────────────────────────────────────────────── */
function TableNode({ data, id, selected }: NodeProps) {
  const { setNodes, getNodes } = useReactFlow();
  const { workflowId, onNodeUpdate, multiSelectedIds, compactMode, detailNodeId, setDetailNodeId, getRunStatus, getRunOutput } = useWorkflowContext();
  const detailOpen = detailNodeId === id;

  const nodeData = data as Record<string, unknown>;
  const runStatus = (getRunStatus(id) as RunStatus) || (nodeData._runStatusHint as RunStatus) || 'idle';
  const runOutput = getRunOutput(id);
  const statusCfg = STATUS_CONFIG[runStatus];

  const ports = getNodePorts('table');
  const inputPorts = ports.filter((p) => p.direction === 'input');
  const outputPorts = ports.filter((p) => p.direction === 'output');

  const canRun = runStatus !== 'running' && !!workflowId;
  const isMultiSelected = selected && multiSelectedIds.size > 0 && multiSelectedIds.has(id);

  const handleRun = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!canRun || !workflowId) return;

      // Use lightweight _runStatusHint instead of full _runStatus + _runOutput
      setNodes((nds) =>
        nds.map((n) =>
          n.id === id ? { ...n, data: { ...n.data, _runStatusHint: 'running' } } : n,
        ),
      );

      const allNodes = getNodes();
      const nodeDataOverrides: Record<string, any> = {};
      nodeDataOverrides[id] = {};
      for (const n of allNodes) {
        if (n.id !== id) {
          const nodeOutput = getRunOutput(n.id);
          if (nodeOutput && !nodeOutput.error) nodeDataOverrides[n.id] = nodeOutput;
        }
      }

      FlowApi.runNodeWS(
        workflowId, id, nodeDataOverrides, onNodeUpdate,
        (_status, error) => { if (error) console.error('[TableNode] run error:', error); },
      );
    },
    [id, setNodes, canRun, workflowId, onNodeUpdate, getNodes, getRunOutput],
  );

  const borderColor =
    runStatus === 'success' ? '#52c41a'
    : runStatus === 'error'   ? '#ff4d4f'
    : runStatus === 'running' ? '#1890ff'
    : selected                ? '#1890ff'
    : '#d9d9d9';

  // Parse tables from output
  const tables: TableData[] | null = (() => {
    if (!runOutput || runStatus === 'idle' || runStatus === 'running') return null;
    if (runOutput.error) return null;
    if (Array.isArray(runOutput.tables)) return runOutput.tables as TableData[];
    return null;
  })();

  const fields: NodeField[] = [];

  return (
    <>
      <div
        className={isMultiSelected ? 'node-multi-selected' : undefined}
        data-multi-selected={isMultiSelected ? 'true' : undefined}
        style={{
          background: '#fff',
          border: `2px solid ${borderColor}`,
          borderRadius: 8,
          minWidth: 280,
          maxWidth: 480,
          fontSize: 12,
          position: 'relative',
        }}
      >
        {/* ===== Header ===== */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 10px 6px', borderBottom: '1px solid #f0f0f0',
        }}>
          <div style={{ fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 4 }}>
            {(data as any)._seq != null && <SeqBadge seq={(data as any)._seq} />}
            <span style={{ fontSize: 16 }}>📊</span>
            <span>Table</span>
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              onClick={(e) => { e.stopPropagation(); setDetailNodeId(id); }}
              title="查看详情"
              style={{
                width: 24, height: 24, borderRadius: 4, border: 'none',
                background: '#f0f5ff', color: '#1890ff', cursor: 'pointer',
                fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: 0, flexShrink: 0,
              }}
            >
              <ExpandOutlined />
            </button>
            <button
              onClick={handleRun}
              disabled={!canRun}
              title={!canRun ? '请先连接上游节点或配置工作流' : statusCfg.title}
              style={{
                width: 24, height: 24, borderRadius: 4, border: 'none',
                background: !canRun ? '#f5f5f5' : statusCfg.bg,
                color: !canRun ? '#d9d9d9' : statusCfg.color,
                cursor: !canRun ? 'not-allowed' : runStatus === 'running' ? 'wait' : 'pointer',
                fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: 0, flexShrink: 0, opacity: !canRun ? 0.5 : 1,
              }}
            >
              {React.createElement(canRun ? statusCfg.icon : PlayCircleOutlined, { spin: canRun && runStatus === 'running' })}
            </button>
          </div>
        </div>

        {/* ===== Port Row ===== */}
        <div style={{ display: 'flex', borderBottom: '1px solid #f0f0f0', padding: '6px 0' }}>
          {/* Input ports */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4, paddingLeft: 22, position: 'relative' }}>
            {inputPorts.map((p) => (
              <div key={p.key} style={{
                display: 'flex', alignItems: 'center',
                fontSize: 10, color: PORT_COLORS[p.type] || '#999',
                position: 'relative', height: 20,
              }}>
                <Handle
                  type="target" position={Position.Left} id={p.key}
                  style={{
                    position: 'absolute', left: -15, top: '50%',
                    transform: 'translateY(-50%)',
                    width: 10, height: 10,
                    background: PORT_COLORS[p.type] || '#d9d9d9',
                    border: '2px solid #fff', boxShadow: '0 0 0 1px rgba(0,0,0,0.1)',
                  }}
                />
                <span>{p.label}</span>
              </div>
            ))}
          </div>
          {/* Output ports */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4, paddingRight: 22, textAlign: 'right', position: 'relative' }}>
            {outputPorts.map((p) => (
              <div key={p.key} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'flex-end',
                fontSize: 10, color: PORT_COLORS[p.type] || '#999',
                position: 'relative', height: 20,
              }}>
                <span>{p.label}</span>
                <Handle
                  type="source" position={Position.Right} id={p.key}
                  style={{
                    position: 'absolute', right: -15, top: '50%',
                    transform: 'translateY(-50%)',
                    width: 10, height: 10,
                    background: PORT_COLORS[p.type] || '#d9d9d9',
                    border: '2px solid #fff', boxShadow: '0 0 0 1px rgba(0,0,0,0.1)',
                  }}
                />
              </div>
            ))}
          </div>
        </div>

        {/* ===== Content ===== */}
        <div style={{ padding: '8px 10px' }}>
          {/* Error — compact mode only shows status badge */}
          {runStatus === 'error' && runOutput && !compactMode && (
            <div style={{ background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: 4, overflow: 'hidden' }}>
              <div style={{ padding: '3px 6px', fontWeight: 600, fontSize: 10, color: '#cf1322', display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#ff4d4f', display: 'inline-block' }} />
                错误
              </div>
              <div style={{ padding: '4px 6px', maxHeight: 80, overflowY: 'auto', borderTop: '1px solid #ffccc7', fontSize: 9 }}
                   className="nowheel nopan">
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: '#cf1322' }}>
                  {typeof runOutput === 'string' ? runOutput : runOutput.error || JSON.stringify(runOutput, null, 2)}
                </pre>
              </div>
            </div>
          )}

          {/* Compact mode: show only status badge */}
          {compactMode && runOutput && runStatus !== 'idle' && runStatus !== 'running' && (
            <div style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 4, fontSize: 10 }}>
              {runStatus === 'error' ? (
                <span style={{ color: '#cf1322' }}>❌ 错误</span>
              ) : (
                <span style={{ color: '#389e0d' }}>✅ 已执行</span>
              )}
            </div>
          )}

          {/* Tables — antd Table with search — hidden in compact mode */}
          {!compactMode && tables && tables.length > 0 && (
            <div className="nowheel nopan">
              {tables.map((t, i) => (
                <MiniTable key={i} table={t} maxRows={50} compact={tables.length > 1} />
              ))}
            </div>
          )}

          {/* Idle hint */}
          {runStatus === 'idle' && (
            <div style={{ fontSize: 10, color: '#bfbfbf', textAlign: 'center', padding: '6px 0' }}>
              连接上游数据节点后点击 ▶ 运行
            </div>
          )}
        </div>
      </div>

      <NodeDetailModal
        open={detailOpen}
        onClose={() => setDetailNodeId(null)}
        nodeId={id}
        nodeType="table"
        icon="📊"
        label="Table"
        fields={fields}
      />
    </>
  );
}

export { MiniTable };
export type { TableData };
export default memo(TableNode);
