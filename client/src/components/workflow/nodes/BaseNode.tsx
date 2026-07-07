import React, { useCallback, lazy, Suspense, useMemo } from 'react';
import { Handle, Position, useReactFlow } from 'reactflow';
import { PlayCircleOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { FlowApi } from '../services/FlowApi';
import { getNodePorts } from '../PortTypes';
import { NodeEventBus } from '../NodeEventBus';

// Lazy load renderers to reduce initial bundle
const ExcelRenderer = lazy(() => import('./Excel/ExcelRenderer'));
const JsonRenderer = lazy(() => import('./Json/JsonRenderer'));
const LuaRenderer = lazy(() => import('./Lua/LuaRenderer'));

export type RunStatus = 'idle' | 'running' | 'success' | 'error';

export interface NodeField {
  key: string;
  label: string;
  placeholder?: string;
  type?: 'text' | 'textarea' | 'number' | 'select' | 'multiselect';
  rows?: number;
  step?: number;
  options?: { label: string; value: string }[];
  required?: boolean;
}

interface BaseNodeProps {
  data: Record<string, unknown>;
  id: string;
  selected: boolean;
  icon: string;
  label: string;
  nodeType: string;
  fields: NodeField[];
}

const STATUS_CONFIG = {
  idle: { color: '#8c8c8c', bg: '#f5f5f5', icon: PlayCircleOutlined, title: '运行节点' },
  running: { color: '#1890ff', bg: '#e6f7ff', icon: LoadingOutlined, title: '运行中...' },
  success: { color: '#52c41a', bg: '#f6ffed', icon: CheckCircleOutlined, title: '运行成功' },
  error: { color: '#ff4d4f', bg: '#fff2f0', icon: CloseCircleOutlined, title: '运行失败' },
};

const PORT_COLORS: Record<string, string> = {
  'file-content': '#1890ff',
  'file-path': '#722ed1',
  'any': '#8c8c8c',
  'text': '#fa8c16',
  'table-data': '#52c41a',
  'json-data': '#13c2c2',
};

const BaseNode: React.FC<BaseNodeProps> = ({
  data,
  id,
  selected,
  icon,
  label,
  nodeType,
  fields,
}) => {
  const { setNodes, getNodes, getEdges } = useReactFlow();

  const runStatus = (data._runStatus as RunStatus) || 'idle';
  const runOutput = data._runOutput as any;
  const statusCfg = STATUS_CONFIG[runStatus];

  const ports = getNodePorts(nodeType);
  const inputPorts = ports.filter((p) => p.direction === 'input');
  const outputPorts = ports.filter((p) => p.direction === 'output');

  // Collect upstream input data from connected nodes
  const upstreamInput = useMemo(() => {
    const edges = getEdges();
    const incomingEdges = edges.filter((e) => e.target === id && e.targetHandle);
    const nodes = getNodes();
    const input: Record<string, any> = {};
    for (const edge of incomingEdges) {
      const srcNode = nodes.find((n) => n.id === edge.source);
      if (!srcNode) continue;
      const srcOutput = (srcNode.data as any)?._runOutput;
      if (!srcOutput || srcOutput.error) continue;
      // Map source handle → target handle
      if (edge.sourceHandle && srcOutput[edge.sourceHandle] !== undefined) {
        input[edge.targetHandle || edge.sourceHandle] = srcOutput[edge.sourceHandle];
      } else {
        Object.assign(input, srcOutput);
      }
    }
    return input;
  }, [id, getEdges, getNodes]);

  // Check if all required fields are filled
  const canRun = useMemo(() => {
    if (runStatus === 'running') return false;
    return fields
      .filter((f) => f.required)
      .every((f) => {
        const val = data[f.key];
        if (f.type === 'multiselect') return Array.isArray(val) && val.length > 0;
        return val !== undefined && val !== null && String(val).trim() !== '';
      });
  }, [fields, data, runStatus]);

  const missingRequired = useMemo(
    () => fields.filter((f) => f.required && !data[f.key]),
    [fields, data],
  );

  const handleFieldChange = useCallback(
    (key: string, value: any) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === id ? { ...n, data: { ...n.data, [key]: value } } : n,
        ),
      );
    },
    [id, setNodes],
  );

  const handleRun = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!canRun) return;

      setNodes((nds) =>
        nds.map((n) =>
          n.id === id ? { ...n, data: { ...n.data, _runStatus: 'running', _runOutput: null } } : n,
        ),
      );

      try {
        const result = await FlowApi.runNode(nodeType, data, upstreamInput);
        const output = result.output ?? result;
        const newStatus = output?.error ? 'error' : 'success';
        setNodes((nds) =>
          nds.map((n) =>
            n.id === id
              ? { ...n, data: { ...n.data, _runStatus: newStatus, _runOutput: output } }
              : n,
          ),
        );
        // Notify event bus for cascade execution
        if (newStatus === 'success') {
          NodeEventBus.emit(id, output);
        }
      } catch (err: any) {
        setNodes((nds) =>
          nds.map((n) =>
            n.id === id
              ? {
                  ...n,
                  data: {
                    ...n.data,
                    _runStatus: 'error',
                    _runOutput: { error: err.message },
                  },
                }
              : n,
          ),
        );
      }
    },
    [id, nodeType, data, setNodes, canRun, upstreamInput],
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

  return (
    <div
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
      {/* ===== Section 1: Header ===== */}
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
          <span style={{ fontSize: 16 }}>{icon}</span>
          <span>{label}</span>
        </div>
        <button
          onClick={handleRun}
          disabled={!canRun}
          title={!canRun ? `请填写必填项: ${missingRequired.map((f) => f.label).join(', ')}` : statusCfg.title}
          style={{
            width: 24,
            height: 24,
            borderRadius: 4,
            border: 'none',
            background: !canRun ? '#f5f5f5' : statusCfg.bg,
            color: !canRun ? '#d9d9d9' : statusCfg.color,
            cursor: !canRun ? 'not-allowed' : runStatus === 'running' ? 'wait' : 'pointer',
            fontSize: 14,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 0,
            flexShrink: 0,
            transition: 'all 0.2s',
            opacity: !canRun ? 0.5 : 1,
          }}
        >
          {React.createElement(canRun ? statusCfg.icon : PlayCircleOutlined, { spin: canRun && runStatus === 'running' })}
        </button>
      </div>

      {/* ===== Section 2: Port row ===== */}
      {(inputPorts.length > 0 || outputPorts.length > 0) && (
        <div
          style={{
            display: 'flex',
            borderBottom: '1px solid #f0f0f0',
            padding: '6px 0',
          }}
        >
          {/* Left column: input ports with inline Handles */}
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
                <span style={{ marginLeft: 0 }}>{p.label}</span>
              </div>
            ))}
          </div>
          {/* Right column: output ports with inline Handles */}
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
                <span style={{ marginRight: 0 }}>{p.label}</span>
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
      )}

      {/* ===== Section 3: Content — fields + output ===== */}
      <div style={{ padding: '8px 10px' }}>
        {fields.map((f) => {
          const val = (data[f.key] as any) ?? (f.type === 'multiselect' ? [] : '');

          if (f.type === 'textarea') {
            return (
              <div key={f.key} style={{ marginBottom: 6 }}>
                <label style={{ display: 'block', fontSize: 10, color: '#888', marginBottom: 2 }}>
                  {f.label}{f.required && <span style={{ color: '#ff4d4f', marginLeft: 2 }}>*</span>}
                </label>
                <textarea
                  value={val}
                  onChange={(e) => handleFieldChange(f.key, e.target.value)}
                  placeholder={f.placeholder}
                  rows={f.rows || 3}
                  onClick={(e) => e.stopPropagation()}
                  onMouseDown={(e) => e.stopPropagation()}
                  style={{
                    width: '100%',
                    fontSize: 11,
                    padding: '3px 6px',
                    border: `1px solid ${f.required && !val ? '#ffccc7' : '#d9d9d9'}`,
                    borderRadius: 3,
                    resize: 'vertical',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
            );
          }

          if (f.type === 'number') {
            return (
              <div key={f.key} style={{ marginBottom: 6 }}>
                <label style={{ display: 'block', fontSize: 10, color: '#888', marginBottom: 2 }}>
                  {f.label}{f.required && <span style={{ color: '#ff4d4f', marginLeft: 2 }}>*</span>}
                </label>
                <input
                  type="number"
                  value={val}
                  onChange={(e) => handleFieldChange(f.key, parseFloat(e.target.value) || 0)}
                  placeholder={f.placeholder}
                  step={f.step}
                  onClick={(e) => e.stopPropagation()}
                  onMouseDown={(e) => e.stopPropagation()}
                  style={{
                    width: '100%',
                    fontSize: 11,
                    padding: '3px 6px',
                    border: `1px solid ${f.required && !val ? '#ffccc7' : '#d9d9d9'}`,
                    borderRadius: 3,
                    boxSizing: 'border-box',
                  }}
                />
              </div>
            );
          }

          if (f.type === 'select' && f.options) {
            return (
              <div key={f.key} style={{ marginBottom: 6 }}>
                <label style={{ display: 'block', fontSize: 10, color: '#888', marginBottom: 2 }}>
                  {f.label}{f.required && <span style={{ color: '#ff4d4f', marginLeft: 2 }}>*</span>}
                </label>
                <select
                  value={val}
                  onChange={(e) => handleFieldChange(f.key, e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                  onMouseDown={(e) => e.stopPropagation()}
                  style={{
                    width: '100%',
                    fontSize: 11,
                    padding: '3px 6px',
                    border: `1px solid ${f.required && !val ? '#ffccc7' : '#d9d9d9'}`,
                    borderRadius: 3,
                    boxSizing: 'border-box',
                    background: '#fff',
                  }}
                >
                  <option value="">-- 选择 --</option>
                  {f.options.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
            );
          }

          if (f.type === 'multiselect' && f.options) {
            const selected: string[] = Array.isArray(val) ? val : [];
            return (
              <div key={f.key} style={{ marginBottom: 6 }}>
                <label style={{ display: 'block', fontSize: 10, color: '#888', marginBottom: 2 }}>
                  {f.label}{f.required && <span style={{ color: '#ff4d4f', marginLeft: 2 }}>*</span>}
                  {selected.length > 0 && (
                    <span style={{ color: '#1890ff', marginLeft: 4 }}>({selected.length})</span>
                  )}
                </label>
                <div
                  style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxHeight: 100, overflowY: 'auto' }}
                  onClick={(e) => e.stopPropagation()}
                  onMouseDown={(e) => e.stopPropagation()}
                >
                  {f.options.length === 0 && (
                    <span style={{ fontSize: 10, color: '#999' }}>运行后加载选项</span>
                  )}
                  {f.options.map((opt) => {
                    const isSelected = selected.includes(opt.value);
                    return (
                      <span
                        key={opt.value}
                        onClick={(e) => {
                          e.stopPropagation();
                          const next = isSelected
                            ? selected.filter((s) => s !== opt.value)
                            : [...selected, opt.value];
                          handleFieldChange(f.key, next);
                        }}
                        style={{
                          padding: '2px 8px',
                          fontSize: 10,
                          border: `1px solid ${isSelected ? '#1890ff' : '#d9d9d9'}`,
                          borderRadius: 3,
                          background: isSelected ? '#e6f7ff' : '#fff',
                          color: isSelected ? '#1890ff' : '#666',
                          cursor: 'pointer',
                          userSelect: 'none',
                        }}
                      >
                        {opt.label}
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          }

          // Default: text input
          return (
            <div key={f.key} style={{ marginBottom: 6 }}>
              <label style={{ display: 'block', fontSize: 10, color: '#888', marginBottom: 2 }}>
                {f.label}{f.required && <span style={{ color: '#ff4d4f', marginLeft: 2 }}>*</span>}
              </label>
              <input
                type="text"
                value={val}
                onChange={(e) => handleFieldChange(f.key, e.target.value)}
                placeholder={f.placeholder}
                onClick={(e) => e.stopPropagation()}
                onMouseDown={(e) => e.stopPropagation()}
                style={{
                  width: '100%',
                  fontSize: 11,
                  padding: '3px 6px',
                  border: `1px solid ${f.required && !val ? '#ffccc7' : '#d9d9d9'}`,
                  borderRadius: 3,
                  boxSizing: 'border-box',
                }}
              />
            </div>
          );
        })}

        {/* Run output — typed renderer */}
        {runOutput && runStatus !== 'idle' && runStatus !== 'running' && (
          <div
            style={{
              marginTop: 6,
              background: runStatus === 'error' ? '#fff2f0' : '#f6ffed',
              border: `1px solid ${runStatus === 'error' ? '#ffccc7' : '#b7eb8f'}`,
              borderRadius: 4,
              overflow: 'hidden',
            }}
          >
            <div style={{ padding: '3px 6px', fontWeight: 600, fontSize: 10, color: runStatus === 'error' ? '#cf1322' : '#389e0d' }}>
              {runStatus === 'error' ? '❌ 错误' : '✅ 结果'}
            </div>
            <div
              style={{
                padding: '4px 6px',
                maxHeight: 200,
                overflowY: 'auto',
                fontSize: 9,
                color: '#333',
                borderTop: `1px solid ${runStatus === 'error' ? '#ffccc7' : '#b7eb8f'}`,
              }}
            >
              {runStatus === 'error' ? (
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {typeof runOutput === 'string' ? runOutput : runOutput.error || JSON.stringify(runOutput, null, 2)}
                </pre>
              ) : nodeType === 'excel' && runOutput.columns ? (
                <Suspense fallback={<pre style={{ margin: 0 }}>{JSON.stringify(runOutput, null, 2).slice(0, 100)}...</pre>}>
                  <ExcelRenderer data={runOutput} columnFilter={(data.columnFilter as string[]) || []} rowFilter={(data.rowFilter as string[]) || []} />
                </Suspense>
              ) : nodeType === 'json' && runOutput.data ? (
                <Suspense fallback={<pre style={{ margin: 0 }}>{JSON.stringify(runOutput, null, 2).slice(0, 100)}...</pre>}>
                  <JsonRenderer data={runOutput.data} jsonPath={runOutput.path} />
                </Suspense>
              ) : nodeType === 'lua' && runOutput.content ? (
                <Suspense fallback={<pre style={{ margin: 0 }}>{runOutput.content?.slice(0, 100)}...</pre>}>
                  <LuaRenderer content={runOutput.content} functionName={runOutput.functionName} functionContent={runOutput.functionContent} />
                </Suspense>
              ) : typeof runOutput === 'string' ? (
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {runOutput}
                </pre>
              ) : runOutput.fileContent && typeof runOutput.fileContent === 'string' ? (
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 160, overflowY: 'auto' }}>
                  {runOutput.fileContent}
                </pre>
              ) : (
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {JSON.stringify(runOutput, null, 2)}
                </pre>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default BaseNode;
