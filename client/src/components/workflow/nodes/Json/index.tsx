/**
 * JsonNode
 * - 接受上游文件内容（fileContent 端口）
 * - jsonPath 参数支持两种模式（互斥）：
 *   1. 直接在节点上手动输入 JSON Path 字符串
 *   2. 通过连线从上游节点（如 String 节点）获取
 * - 两者同时存在时，连线优先，并在节点上显示警告提示
 */

import React, { memo, useCallback, useState, useEffect } from 'react';
import { NodeProps, Handle, Position, useReactFlow, useStore } from 'reactflow';
import {
  PlayCircleOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  InfoCircleOutlined,
  ExpandOutlined,
} from '@ant-design/icons';
import { FlowApi } from '../../services/FlowApi';
import { getNodePorts } from '../../PortTypes';
import { useWorkflowContext } from '../../WorkflowContext';
import NodeDetailModal from '../NodeDetailModal';
import { NodeField, FieldTextInput } from '../BaseNode';

type RunStatus = 'idle' | 'running' | 'success' | 'error';

const STATUS_CONFIG = {
  idle: { color: '#8c8c8c', bg: '#f5f5f5', icon: PlayCircleOutlined, title: '运行节点' },
  running: { color: '#1890ff', bg: '#e6f7ff', icon: LoadingOutlined, title: '运行中...' },
  success: { color: '#52c41a', bg: '#f6ffed', icon: CheckCircleOutlined, title: '运行成功' },
  error: { color: '#ff4d4f', bg: '#fff2f0', icon: CloseCircleOutlined, title: '运行失败' },
};

const PORT_COLORS: Record<string, string> = {
  'file-content': '#1890ff',
  'json-path': '#722ed1',
  'json-data': '#13c2c2',
  'any': '#8c8c8c',
};

function JsonNode({ data, id, selected }: NodeProps) {
  const { setNodes, getNodes } = useReactFlow();
  const { workflowId, onNodeUpdate, multiSelectedIds, compactMode, detailNodeId, setDetailNodeId } = useWorkflowContext();
  const detailOpen = detailNodeId === id;
  const [overrideWarning, setOverrideWarning] = useState(false);

  const nodeData = data as Record<string, unknown>;
  const runStatus = (nodeData._runStatus as RunStatus) || 'idle';
  const runOutput = nodeData._runOutput as any;
  const statusCfg = STATUS_CONFIG[runStatus];

  const ports = getNodePorts('json');
  const inputPorts = ports.filter((p) => p.direction === 'input');
  const outputPorts = ports.filter((p) => p.direction === 'output');

  // 检测 jsonPath 端口是否有连线
  const hasJsonPathEdge = useStore(
    useCallback(
      (s) => s.edges.some((e) => e.target === id && e.targetHandle === 'jsonPath'),
      [id],
    ),
  );

  // 检测 fileContent 端口是否有连线
  const hasFileContentEdge = useStore(
    useCallback(
      (s) => s.edges.some((e) => e.target === id && e.targetHandle === 'fileContent'),
      [id],
    ),
  );

  const manualJsonPath = nodeData.jsonPath as string | undefined;

  // 当连线接入 jsonPath 且手动有值时，展示覆盖警告
  useEffect(() => {
    if (hasJsonPathEdge && manualJsonPath && manualJsonPath.trim() !== '') {
      setOverrideWarning(true);
      const timer = setTimeout(() => setOverrideWarning(false), 4000);
      return () => clearTimeout(timer);
    }
  }, [hasJsonPathEdge]);

  const handleJsonPathChange = useCallback(
    (val: string) => {
      if (hasJsonPathEdge) return;
      setNodes((nds) =>
        nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, jsonPath: val } } : n)),
      );
    },
    [id, setNodes, hasJsonPathEdge],
  );

  // JSON 节点可运行：有 fileContent 连线，或有 workflowId（由后端整图推送）
  const canRun = runStatus !== 'running' && (hasFileContentEdge || !!workflowId);

  const handleRun = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!canRun) return;

      if (!workflowId) {
        console.warn('[JsonNode] No workflowId, cannot run via WebSocket');
        return;
      }

      // Mark this node as running immediately
      setNodes((nds) =>
        nds.map((n) =>
          n.id === id ? { ...n, data: { ...n.data, _runStatus: 'running', _runOutput: null } } : n,
        ),
      );

      // Build node data overrides: current node config + other nodes' cached outputs
      const allNodes = getNodes();
      const nodeDataOverrides: Record<string, any> = {};

      // Override current node's config with latest field values
      const cleanConfig: Record<string, any> = {};
      if (!hasJsonPathEdge && manualJsonPath) {
        cleanConfig.jsonPath = manualJsonPath;
      }
      nodeDataOverrides[id] = cleanConfig;

      // Pass cached outputs of other nodes for upstream context
      for (const n of allNodes) {
        if (n.id !== id) {
          const runOutput = (n.data as any)?._runOutput;
          if (runOutput && !runOutput.error) {
            nodeDataOverrides[n.id] = runOutput;
          }
        }
      }

      FlowApi.runNodeWS(
        workflowId,
        id,
        nodeDataOverrides,
        onNodeUpdate,
        (_status, error) => {
          if (error) console.error('[JsonNode] NodeRun error:', error);
        },
      );
    },
    [id, setNodes, canRun, workflowId, onNodeUpdate, getNodes, hasJsonPathEdge, manualJsonPath],
  );

  // Display the upstream jsonPath value (from other node's _runOutput)
  const upstreamJsonPath = useStore(
    useCallback(
      (s) => {
        if (!hasJsonPathEdge) return undefined;
        const edge = s.edges.find((e) => e.target === id && e.targetHandle === 'jsonPath');
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
      [id, hasJsonPathEdge],
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

  // Whether this node is part of a multi-selection
  const isMultiSelected = selected && multiSelectedIds.size > 0 && multiSelectedIds.has(id);

  const fields: NodeField[] = [
    { key: 'jsonPath', label: 'JSON Path', placeholder: '$.data.items（可选）', linkedPortKey: 'jsonPath' },
  ];

  return (
    <>
      <div
        className={isMultiSelected ? 'node-multi-selected' : undefined}
        data-multi-selected={isMultiSelected ? 'true' : undefined}
        style={{
          background: '#fff',
          border: `2px solid ${borderColor}`,
          borderRadius: 8,
          minWidth: 220,
          maxWidth: 300,
          fontSize: 12,
          position: 'relative',
        }}
      >
        {/* ===== Header ===== */}
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
            <span style={{ fontSize: 16 }}>📋</span>
            <span>JSON</span>
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
              title={!canRun ? '请先连接文件内容输入或配置工作流' : statusCfg.title}
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

        {/* ===== Port Row ===== */}
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
                  {p.key === 'jsonPath' && hasJsonPathEdge && (
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
                <span>{p.label}</span>
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

        {/* ===== Content ===== */}
        <div style={{ padding: '8px 10px' }}>
          {/* Override warning */}
          {overrideWarning && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 4,
              padding: '4px 6px', marginBottom: 6,
              background: '#fffbe6', border: '1px solid #ffe58f', borderRadius: 4,
              fontSize: 10, color: '#d48806',
            }}>
              <InfoCircleOutlined />
              <span>连线输入已覆盖手动填写的 JSON Path</span>
            </div>
          )}

          {/* JSON Path field */}
          <div style={{ marginBottom: 6 }}>
            <label style={{ display: 'block', fontSize: 10, color: '#888', marginBottom: 2 }}>
              JSON Path
              {hasJsonPathEdge ? (
                <span style={{ color: '#2f54eb', marginLeft: 4 }}>🔗 由连线提供</span>
              ) : (
                <span style={{ color: '#999', marginLeft: 4 }}>(可选，也可连线输入)</span>
              )}
            </label>
            {hasJsonPathEdge ? (
              <input
                className="nodrag"
                type="text"
                value={upstreamJsonPath ?? '...等待上游运行'}
                readOnly
                placeholder="由连线提供"
                style={{
                  width: '100%', fontSize: 11, padding: '3px 6px',
                  border: '1px solid #d9d9d9', borderRadius: 3, boxSizing: 'border-box',
                  background: '#f5f5f5', color: '#aaa', cursor: 'not-allowed',
                }}
              />
            ) : (
              <FieldTextInput
                value={manualJsonPath ?? ''}
                placeholder="$.data.items（可选）"
                onChange={handleJsonPathChange}
                style={{
                  width: '100%', fontSize: 11, padding: '3px 6px',
                  border: '1px solid #d9d9d9', borderRadius: 3, boxSizing: 'border-box',
                  background: '#fff', color: '#333', cursor: 'text',
                }}
              />
            )}
          </div>

          {/* Run output */}
          {runOutput && runStatus !== 'idle' && runStatus !== 'running' && (
            compactMode ? (
              <div style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 4, fontSize: 10 }}>
                {runStatus === 'error' ? (
                  <span style={{ color: '#cf1322' }}>❌ 错误</span>
                ) : (
                  <span style={{ color: '#389e0d' }}>✅ 已执行</span>
                )}
              </div>
            ) : (
            <div style={{ marginTop: 6 }}>
              {runStatus === 'error' ? (
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
              ) : (
                outputPorts.map((p) => {
                  const portValue = runOutput?.[p.key];
                  const hasValue = portValue !== undefined && portValue !== null;
                  const displayValue = hasValue ? portValue : (outputPorts.length === 1 ? runOutput : undefined);
                  const hasDisplay = displayValue !== undefined && displayValue !== null;

                  return (
                    <div key={p.key} style={{ marginBottom: 4, background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 4, overflow: 'hidden' }}>
                      <div style={{ padding: '3px 6px', fontWeight: 600, fontSize: 10, color: '#389e0d', display: 'flex', alignItems: 'center', gap: 4 }}>
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: PORT_COLORS[p.type] || '#52c41a', display: 'inline-block' }} />
                        {p.label}{hasDisplay ? ' ✅' : ''}
                      </div>
                      {hasDisplay && (
                        <div style={{ padding: '4px 6px', maxHeight: 120, overflowY: 'auto', fontSize: 9, borderTop: '1px solid #b7eb8f' }}
                             className="nowheel nopan">
                          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                            {typeof displayValue === 'string' ? displayValue : JSON.stringify(displayValue, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
            ) /* end compactMode ternary */
          )}
        </div>
      </div>

      <NodeDetailModal
        open={detailOpen}
        onClose={() => setDetailNodeId(null)}
        nodeId={id}
        nodeType="json"
        icon="📋"
        label="JSON"
        fields={fields}
      />
    </>
  );
}

export default memo(JsonNode);
