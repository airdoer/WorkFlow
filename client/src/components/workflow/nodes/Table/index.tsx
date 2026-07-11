/**
 * TableNode
 * - 接受上游数据（tableInput 端口：string / json-data / any）
 * - 解析为结构化表格：数组 → 单表，字典 → 多表
 * - 在节点卡片中直接渲染表格预览
 */

import React, { memo, useCallback, useState } from 'react';
import { NodeProps, Handle, Position, useReactFlow } from 'reactflow';
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
import { NodeField } from '../BaseNode';

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

function MiniTable({ table, maxRows = 20 }: { table: TableData; maxRows?: number }) {
  const { title, columns, rows } = table;
  const visibleRows = rows.slice(0, maxRows);
  const truncated = rows.length > maxRows;

  return (
    <div style={{ marginBottom: 8 }}>
      {title && (
        <div style={{
          fontSize: 10, fontWeight: 600, color: '#595959',
          padding: '2px 4px', background: '#f0f5ff',
          borderRadius: '3px 3px 0 0', borderBottom: '1px solid #d6e4ff',
        }}>
          {title}
        </div>
      )}
      <div style={{ overflowX: 'auto' }} className="nowheel nopan">
        <table style={{
          width: '100%', borderCollapse: 'collapse',
          fontSize: 10, tableLayout: 'auto',
        }}>
          <thead>
            <tr>
              {columns.map((col, i) => (
                <th key={i} style={{
                  padding: '2px 6px', background: '#fafafa',
                  border: '1px solid #e8e8e8', color: '#262626',
                  fontWeight: 600, whiteSpace: 'nowrap', textAlign: 'left',
                }}>
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} style={{
                  padding: '4px 6px', border: '1px solid #e8e8e8',
                  color: '#bfbfbf', textAlign: 'center', fontStyle: 'italic',
                }}>
                  (空)
                </td>
              </tr>
            ) : (
              visibleRows.map((row, ri) => (
                <tr key={ri} style={{ background: ri % 2 === 0 ? '#fff' : '#fafafa' }}>
                  {row.map((cell, ci) => (
                    <td key={ci} style={{
                      padding: '2px 6px', border: '1px solid #e8e8e8',
                      color: '#262626', maxWidth: 160,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {truncated && (
        <div style={{ fontSize: 9, color: '#8c8c8c', padding: '2px 4px' }}>
          … 仅显示前 {maxRows} 行，共 {rows.length} 行
        </div>
      )}
    </div>
  );
}

/* ─── TableNode ─────────────────────────────────────────────────────────── */
function TableNode({ data, id, selected }: NodeProps) {
  const { setNodes, getNodes } = useReactFlow();
  const { workflowId, onNodeUpdate, multiSelectedIds } = useWorkflowContext();
  const [detailOpen, setDetailOpen] = useState(false);

  const nodeData = data as Record<string, unknown>;
  const runStatus = (nodeData._runStatus as RunStatus) || 'idle';
  const runOutput = nodeData._runOutput as any;
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

      setNodes((nds) =>
        nds.map((n) =>
          n.id === id ? { ...n, data: { ...n.data, _runStatus: 'running', _runOutput: null } } : n,
        ),
      );

      const allNodes = getNodes();
      const nodeDataOverrides: Record<string, any> = {};
      nodeDataOverrides[id] = {};
      for (const n of allNodes) {
        if (n.id !== id) {
          const ro = (n.data as any)?._runOutput;
          if (ro && !ro.error) nodeDataOverrides[n.id] = ro;
        }
      }

      FlowApi.runNodeWS(
        workflowId, id, nodeDataOverrides, onNodeUpdate,
        (_status, error) => { if (error) console.error('[TableNode] run error:', error); },
      );
    },
    [id, setNodes, canRun, workflowId, onNodeUpdate, getNodes],
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
          minWidth: 240,
          maxWidth: 420,
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
            <span style={{ fontSize: 16 }}>📊</span>
            <span>Table</span>
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              onClick={(e) => { e.stopPropagation(); setDetailOpen(true); }}
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
          {/* Error */}
          {runStatus === 'error' && runOutput && (
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

          {/* Tables */}
          {tables && tables.length > 0 && (
            <div style={{ maxHeight: 320, overflowY: 'auto' }} className="nowheel nopan">
              {tables.map((t, i) => (
                <MiniTable key={i} table={t} maxRows={50} />
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
        onClose={() => setDetailOpen(false)}
        nodeId={id}
        nodeType="table"
        icon="📊"
        label="Table"
        fields={fields}
      />
    </>
  );
}

export default memo(TableNode);
