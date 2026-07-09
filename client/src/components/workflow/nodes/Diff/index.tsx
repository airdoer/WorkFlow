/**
 * DiffNode
 * - 接受两个 string 输入（stringA / stringB）
 * - 输出 diffResult（JSON string 格式的 diff 信息）和 isSame（bool 值）
 * - 运行后用 Monaco DiffEditor 展示 side-by-side diff
 */

import React, { memo, useCallback, useState, lazy, Suspense } from 'react';
import { NodeProps, Handle, Position, useReactFlow, useStore } from 'reactflow';
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
import { NodeField, RunStatus } from '../BaseNode';

const DiffRenderer = lazy(() => import('./DiffRenderer'));

const STATUS_CONFIG = {
  idle: { color: '#8c8c8c', bg: '#f5f5f5', icon: PlayCircleOutlined, title: '运行节点' },
  running: { color: '#1890ff', bg: '#e6f7ff', icon: LoadingOutlined, title: '运行中...' },
  success: { color: '#52c41a', bg: '#f6ffed', icon: CheckCircleOutlined, title: '运行成功' },
  error: { color: '#ff4d4f', bg: '#fff2f0', icon: CloseCircleOutlined, title: '运行失败' },
};

const PORT_COLORS: Record<string, string> = {
  'string': '#fa8c16',
  'json-data': '#13c2c2',
  'boolean': '#eb2f96',
  'any': '#8c8c8c',
};

function DiffNode({ data, id, selected }: NodeProps) {
  const { setNodes, getNodes } = useReactFlow();
  const { workflowId, onNodeUpdate, ensureSaved, multiSelectedIds } = useWorkflowContext();
  const [detailOpen, setDetailOpen] = useState(false);

  const nodeData = data as Record<string, unknown>;
  const runStatus = (nodeData._runStatus as RunStatus) || 'idle';
  const runOutput = nodeData._runOutput as any;
  const statusCfg = STATUS_CONFIG[runStatus];

  // Whether this node is part of a multi-selection
  const isMultiSelected = selected && multiSelectedIds.size > 0 && multiSelectedIds.has(id);

  const ports = getNodePorts('diff');
  const inputPorts = ports.filter((p) => p.direction === 'input');
  const outputPorts = ports.filter((p) => p.direction === 'output');

  // 检测输入端口是否有连线
  const hasStringAEdge = useStore(
    useCallback((s) => s.edges.some((e) => e.target === id && e.targetHandle === 'stringA'), [id]),
  );
  const hasStringBEdge = useStore(
    useCallback((s) => s.edges.some((e) => e.target === id && e.targetHandle === 'stringB'), [id]),
  );

  const canRun = runStatus !== 'running' && (hasStringAEdge || hasStringBEdge || !!workflowId);

  const handleRun = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!canRun) return;

      // Ensure workflow is saved before running
      const savedId = await ensureSaved();
      if (!savedId) return;

      // Mark this node as running
      setNodes((nds) =>
        nds.map((n) =>
          n.id === id ? { ...n, data: { ...n.data, _runStatus: 'running', _runOutput: null } } : n,
        ),
      );

      // Build node data overrides
      const allNodes = getNodes();
      const nodeDataOverrides: Record<string, any> = {};
      nodeDataOverrides[id] = {};

      for (const n of allNodes) {
        if (n.id !== id) {
          const runOutput = (n.data as any)?._runOutput;
          if (runOutput && !runOutput.error) {
            nodeDataOverrides[n.id] = runOutput;
          }
        }
      }

      FlowApi.runNodeWS(
        savedId,
        id,
        nodeDataOverrides,
        onNodeUpdate,
        (_status, error) => {
          if (error) console.error('[DiffNode] NodeRun error:', error);
        },
      );
    },
    [id, setNodes, canRun, ensureSaved, onNodeUpdate, getNodes, hasStringAEdge, hasStringBEdge],
  );

  // 获取上游输入的值（用于预览）
  const upstreamStringA = useStore(
    useCallback(
      (s) => {
        if (!hasStringAEdge) return undefined;
        const edge = s.edges.find((e) => e.target === id && e.targetHandle === 'stringA');
        if (!edge) return undefined;
        const srcNode = s.nodeInternals.get(edge.source);
        if (!srcNode) return undefined;
        const srcOutput = (srcNode.data as any)?._runOutput;
        if (!srcOutput) return undefined;
        if (edge.sourceHandle && srcOutput[edge.sourceHandle] !== undefined) {
          return String(srcOutput[edge.sourceHandle]);
        }
        return srcOutput.value !== undefined ? String(srcOutput.value) : undefined;
      },
      [id, hasStringAEdge],
    ),
  );

  const upstreamStringB = useStore(
    useCallback(
      (s) => {
        if (!hasStringBEdge) return undefined;
        const edge = s.edges.find((e) => e.target === id && e.targetHandle === 'stringB');
        if (!edge) return undefined;
        const srcNode = s.nodeInternals.get(edge.source);
        if (!srcNode) return undefined;
        const srcOutput = (srcNode.data as any)?._runOutput;
        if (!srcOutput) return undefined;
        if (edge.sourceHandle && srcOutput[edge.sourceHandle] !== undefined) {
          return String(srcOutput[edge.sourceHandle]);
        }
        return srcOutput.value !== undefined ? String(srcOutput.value) : undefined;
      },
      [id, hasStringBEdge],
    ),
  );

  const borderColor =
    runStatus === 'success'
      ? '#52c41a'
      : runStatus === 'error'
        ? '#ff4d4f'
        : runStatus === 'running'
          ? '#1890ff'
          : selected
            ? '#1890ff'
            : '#d9d9d9';

  const fields: NodeField[] = [];

  // Parse diff output for rendering
  const stringA = runOutput?.stringA ?? upstreamStringA ?? '';
  const stringB = runOutput?.stringB ?? upstreamStringB ?? '';
  const isSameResult = runOutput?.isSame;

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
          maxWidth: 360,
          fontSize: 12,
          position: 'relative',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 10px 6px',
            borderBottom: '1px solid #f0f0f0',
          }}
        >
          <div style={{ fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontSize: 16 }}>🔀</span>
            <span>Diff</span>
            {isSameResult !== undefined && (
              <span
                style={{
                  fontSize: 10,
                  padding: '1px 6px',
                  borderRadius: 8,
                  background: isSameResult ? '#f6ffed' : '#fff2f0',
                  color: isSameResult ? '#52c41a' : '#ff4d4f',
                  border: `1px solid ${isSameResult ? '#b7eb8f' : '#ffccc7'}`,
                }}
              >
                {isSameResult ? '相同' : '不同'}
              </span>
            )}
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
              title={!canRun ? '请先连接输入或配置工作流' : statusCfg.title}
              style={{
                width: 24, height: 24, borderRadius: 4, border: 'none',
                background: !canRun ? '#f5f5f5' : statusCfg.bg,
                color: !canRun ? '#d9d9d9' : statusCfg.color,
                cursor: !canRun ? 'not-allowed' : runStatus === 'running' ? 'wait' : 'pointer',
                fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: 0, flexShrink: 0,
                opacity: !canRun ? 0.5 : 1,
              }}
            >
              {React.createElement(canRun ? statusCfg.icon : PlayCircleOutlined, { spin: canRun && runStatus === 'running' })}
            </button>
          </div>
        </div>

        {/* Port Row */}
        <div style={{ display: 'flex', borderBottom: '1px solid #f0f0f0', padding: '6px 0' }}>
          {/* Input ports */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4, paddingLeft: 22, position: 'relative' }}>
            {inputPorts.map((p) => (
              <div
                key={p.key}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  fontSize: 10,
                  color: PORT_COLORS[p.type] || '#999',
                  position: 'relative',
                  height: 20,
                }}
              >
                <Handle
                  type="target"
                  position={Position.Left}
                  id={p.key}
                  style={{
                    position: 'absolute',
                    left: -15,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    width: 10,
                    height: 10,
                    background: PORT_COLORS[p.type] || '#d9d9d9',
                    border: '2px solid #fff',
                    boxShadow: '0 0 0 1px rgba(0,0,0,0.1)',
                  }}
                />
                <span>
                  {p.label}
                  {p.key === 'stringA' && hasStringAEdge && (
                    <span style={{ color: '#2f54eb', marginLeft: 4 }}>🔗</span>
                  )}
                  {p.key === 'stringB' && hasStringBEdge && (
                    <span style={{ color: '#2f54eb', marginLeft: 4 }}>🔗</span>
                  )}
                </span>
              </div>
            ))}
          </div>
          {/* Output ports */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4, paddingRight: 22, textAlign: 'right', position: 'relative' }}>
            {outputPorts.map((p) => (
              <div
                key={p.key}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-end',
                  fontSize: 10,
                  color: PORT_COLORS[p.type] || '#999',
                  position: 'relative',
                  height: 20,
                }}
              >
                <span>
                  {p.label}
                  {p.key === 'isSame' && isSameResult !== undefined && (
                    <span style={{ marginLeft: 4, color: isSameResult ? '#52c41a' : '#ff4d4f' }}>
                      {isSameResult ? '✅' : '❌'}
                    </span>
                  )}
                </span>
                <Handle
                  type="source"
                  position={Position.Right}
                  id={p.key}
                  style={{
                    position: 'absolute',
                    right: -15,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    width: 10,
                    height: 10,
                    background: PORT_COLORS[p.type] || '#d9d9d9',
                    border: '2px solid #fff',
                    boxShadow: '0 0 0 1px rgba(0,0,0,0.1)',
                  }}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Content: Diff output with Monaco DiffEditor */}
        <div style={{ padding: '6px 8px' }}>
          {runOutput && runStatus === 'success' && stringA !== undefined && stringB !== undefined && (
            <div style={{ marginTop: 4 }}>
              <div
                style={{
                  padding: '3px 6px',
                  fontWeight: 600,
                  fontSize: 10,
                  color: '#389e0d',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  marginBottom: 4,
                }}
              >
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#52c41a', display: 'inline-block' }} />
                Diff 对比
              </div>
              <Suspense
                fallback={
                  <div style={{ height: 200, background: '#f5f5f5', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: '#999' }}>
                    加载 Diff 编辑器...
                  </div>
                }
              >
                <DiffRenderer
                  original={String(stringA)}
                  modified={String(stringB)}
                  language="plaintext"
                  height={200}
                />
              </Suspense>
            </div>
          )}

          {runOutput && runStatus === 'error' && (
            <div style={{ background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: 4, overflow: 'hidden', marginTop: 4 }}>
              <div style={{ padding: '3px 6px', fontWeight: 600, fontSize: 10, color: '#cf1322', display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#ff4d4f', display: 'inline-block' }} />
                错误
              </div>
              <div style={{ padding: '4px 6px', maxHeight: 80, overflowY: 'auto', borderTop: '1px solid #ffccc7', fontSize: 9 }}>
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: '#cf1322' }}>
                  {typeof runOutput === 'string' ? runOutput : runOutput.error || JSON.stringify(runOutput, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>

      <NodeDetailModal
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        nodeId={id}
        nodeType="diff"
        icon="🔀"
        label="Diff"
        fields={fields}
      />
    </>
  );
}

export default memo(DiffNode);
