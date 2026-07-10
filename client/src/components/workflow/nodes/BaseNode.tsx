import React, { useCallback, useState, lazy, Suspense, useMemo } from 'react';
import { Handle, Position, useReactFlow, useStore } from 'reactflow';
import { PlayCircleOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined, ExpandOutlined } from '@ant-design/icons';
import { FlowApi } from '../services/FlowApi';
import { getNodePorts } from '../PortTypes';
import { useWorkflowContext } from '../WorkflowContext';
import NodeDetailModal from './NodeDetailModal';

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
  /** If set, this field is driven by an input port with this key.
   *  When that port has an active connection, the field is locked (read-only).
   */
  linkedPortKey?: string;
  /**
   * Optional custom renderer for this field.
   * When provided, replaces the default input/select rendering.
   * Receives (value, onChange, locked) and should return a React element.
   */
  renderCustomField?: (value: any, onChange: (v: any) => void, locked: boolean) => React.ReactNode;
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
  'boolean': '#eb2f96',
  'string': '#fa8c16',
  'number': '#13c2c2',
  'json-path': '#722ed1',
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
  const { setNodes, getNodes } = useReactFlow();
  const { workflowId, onNodeUpdate, ensureSaved, multiSelectedIds } = useWorkflowContext();
  const [detailOpen, setDetailOpen] = useState(false);

  const runStatus = (data._runStatus as RunStatus) || 'idle';
  const runOutput = data._runOutput as any;
  const statusCfg = STATUS_CONFIG[runStatus];

  // Whether this node is part of a multi-selection
  const isMultiSelected = selected && multiSelectedIds.size > 0 && multiSelectedIds.has(id);

  // Reactively track which input ports are connected via edges
  const connectedInputPorts = useStore(
    useCallback(
      (s) => {
        const result: Record<string, boolean> = {};
        for (const e of s.edges) {
          if (e.target === id && e.targetHandle) {
            result[e.targetHandle] = true;
          }
        }
        return result;
      },
      [id],
    ),
  );

  const ports = getNodePorts(nodeType);
  const inputPorts = ports.filter((p) => p.direction === 'input');
  const outputPorts = ports.filter((p) => p.direction === 'output');

  // Check if all required fields are filled
  // A required field is satisfied if: it has a value, OR its linkedPortKey is connected via an edge
  const canRun = useMemo(() => {
    if (runStatus === 'running') return false;
    return fields
      .filter((f) => f.required)
      .every((f) => {
        if (f.linkedPortKey && connectedInputPorts[f.linkedPortKey]) return true;
        const val = data[f.key];
        if (f.type === 'multiselect') return Array.isArray(val) && val.length > 0;
        return val !== undefined && val !== null && String(val).trim() !== '';
      });
  }, [fields, data, runStatus, connectedInputPorts]);

  const missingRequired = useMemo(
    () => fields.filter((f) => f.required && !data[f.key] && !(f.linkedPortKey && connectedInputPorts[f.linkedPortKey])),
    [fields, data, connectedInputPorts],
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

      // Ensure workflow is saved before running
      const savedId = await ensureSaved();
      if (!savedId) return;

      // Mark this node (and reset downstream) to running immediately for visual feedback
      setNodes((nds) =>
        nds.map((n) =>
          n.id === id ? { ...n, data: { ...n.data, _runStatus: 'running', _runOutput: null } } : n,
        ),
      );

      // Build clean field config for the current node (latest values, may not be saved yet)
      const cleanConfig: Record<string, any> = {};
      for (const f of fields) {
        if (data[f.key] !== undefined && data[f.key] !== null && String(data[f.key]).trim() !== '') {
          cleanConfig[f.key] = data[f.key];
        }
      }

      // Collect all other nodes' last known _runOutput as upstream context
      const allNodes = getNodes();
      const nodeDataOverrides: Record<string, any> = {};
      nodeDataOverrides[id] = cleanConfig;
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
          if (error) {
            console.error('[BaseNode] NodeRun finished with error:', error);
          }
        },
      );
    },
    [id, nodeType, data, fields, setNodes, canRun, ensureSaved, onNodeUpdate, getNodes],
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
        <div style={{ display: 'flex', gap: 4 }}>
          {/* Expand button — opens NodeDetailModal */}
          <button
            onClick={(e) => { e.stopPropagation(); setDetailOpen(true); }}
            title="查看详情"
            style={{
              width: 24, height: 24, borderRadius: 4, border: 'none',
              background: '#f0f5ff', color: '#1890ff', cursor: 'pointer',
              fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
              padding: 0, flexShrink: 0, transition: 'all 0.2s',
            }}
          >
            <ExpandOutlined />
          </button>
          {/* Run button */}
          <button
            onClick={handleRun}
            disabled={!canRun}
            title={!canRun ? `请填写必填项: ${missingRequired.map((f) => f.label).join(', ')}` : statusCfg.title}
            style={{
              width: 24, height: 24, borderRadius: 4, border: 'none',
              background: !canRun ? '#f5f5f5' : statusCfg.bg,
              color: !canRun ? '#d9d9d9' : statusCfg.color,
              cursor: !canRun ? 'not-allowed' : runStatus === 'running' ? 'wait' : 'pointer',
              fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
              padding: 0, flexShrink: 0, transition: 'all 0.2s',
              opacity: !canRun ? 0.5 : 1,
            }}
          >
            {React.createElement(canRun ? statusCfg.icon : PlayCircleOutlined, { spin: canRun && runStatus === 'running' })}
          </button>
        </div>
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
          const locked = !!(f.linkedPortKey && connectedInputPorts[f.linkedPortKey]);
          const val = (data[f.key] as any) ?? (f.type === 'multiselect' ? [] : '');

          const lockedStyle: React.CSSProperties = {
            width: '100%', fontSize: 11, padding: '3px 6px',
            border: '1px solid #d9d9d9', borderRadius: 3, boxSizing: 'border-box',
            background: '#f5f5f5', color: '#bbb', cursor: 'not-allowed',
          };

          const fieldLabel = (
            <label style={{ display: 'block', fontSize: 10, color: '#888', marginBottom: 2 }}>
              {f.label}
              {f.required && !locked && <span style={{ color: '#ff4d4f', marginLeft: 2 }}>*</span>}
              {locked && <span style={{ color: '#2f54eb', marginLeft: 4, fontSize: 9 }}>🔗连线</span>}
            </label>
          );

          if (f.type === 'textarea') {
            return (
              <div key={f.key} style={{ marginBottom: 6 }}>
                {fieldLabel}
                <textarea
                  className="nodrag"
                  value={val}
                  disabled={locked}
                  onChange={(e) => !locked && handleFieldChange(f.key, e.target.value)}
                  placeholder={locked ? '由连线提供' : f.placeholder}
                  rows={f.rows || 3}
                  style={locked ? { ...lockedStyle, resize: 'vertical' } : {
                    width: '100%', fontSize: 11, padding: '3px 6px',
                    border: `1px solid ${f.required && !val ? '#ffccc7' : '#d9d9d9'}`,
                    borderRadius: 3, resize: 'vertical', boxSizing: 'border-box',
                  }}
                />
              </div>
            );
          }

          if (f.type === 'number') {
            return (
              <div key={f.key} style={{ marginBottom: 6 }}>
                {fieldLabel}
                <input
                  className="nodrag"
                  type="number"
                  value={val}
                  disabled={locked}
                  onChange={(e) => !locked && handleFieldChange(f.key, parseFloat(e.target.value) || 0)}
                  placeholder={locked ? '由连线提供' : f.placeholder}
                  step={f.step}
                  style={locked ? lockedStyle : {
                    width: '100%', fontSize: 11, padding: '3px 6px',
                    border: `1px solid ${f.required && !val ? '#ffccc7' : '#d9d9d9'}`,
                    borderRadius: 3, boxSizing: 'border-box',
                  }}
                />
              </div>
            );
          }

          if (f.type === 'select' && f.options) {
            return (
              <div key={f.key} style={{ marginBottom: 6 }}>
                {fieldLabel}
                <select
                  className="nodrag"
                  value={val}
                  disabled={locked}
                  onChange={(e) => !locked && handleFieldChange(f.key, e.target.value)}
                  style={locked ? lockedStyle : {
                    width: '100%', fontSize: 11, padding: '3px 6px',
                    border: `1px solid ${f.required && !val ? '#ffccc7' : '#d9d9d9'}`,
                    borderRadius: 3, boxSizing: 'border-box', background: '#fff',
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
            const selectedVals: string[] = Array.isArray(val) ? val : [];
            return (
              <div key={f.key} style={{ marginBottom: 6 }}>
                {fieldLabel}
                <div
                  className="nodrag"
                  style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxHeight: 100, overflowY: 'auto', opacity: locked ? 0.5 : 1 }}
                >
                  {f.options.length === 0 && (
                    <span style={{ fontSize: 10, color: '#999' }}>运行后加载选项</span>
                  )}
                  {f.options.map((opt) => {
                    const isSelected = selectedVals.includes(opt.value);
                    return (
                      <span
                        key={opt.value}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (locked) return;
                          const next = isSelected
                            ? selectedVals.filter((s) => s !== opt.value)
                            : [...selectedVals, opt.value];
                          handleFieldChange(f.key, next);
                        }}
                        style={{
                          padding: '2px 8px', fontSize: 10,
                          border: `1px solid ${isSelected ? '#1890ff' : '#d9d9d9'}`,
                          borderRadius: 3,
                          background: isSelected ? '#e6f7ff' : '#fff',
                          color: isSelected ? '#1890ff' : '#666',
                          cursor: locked ? 'not-allowed' : 'pointer',
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

          // Custom renderer — takes priority over all default rendering
          if (f.renderCustomField) {
            return (
              <div key={f.key} style={{ marginBottom: 6 }}>
                {fieldLabel}
                {f.renderCustomField(val, (v) => !locked && handleFieldChange(f.key, v), locked)}
              </div>
            );
          }

          // Default: text input
          return (
            <div key={f.key} style={{ marginBottom: 6 }}>
              {fieldLabel}
              <input
                className="nodrag"
                type="text"
                value={val}
                disabled={locked}
                onChange={(e) => !locked && handleFieldChange(f.key, e.target.value)}
                placeholder={locked ? '由连线提供' : f.placeholder}
                style={locked ? lockedStyle : {
                  width: '100%', fontSize: 11, padding: '3px 6px',
                  border: `1px solid ${f.required && !val ? '#ffccc7' : '#d9d9d9'}`,
                  borderRadius: 3, boxSizing: 'border-box',
                }}
              />
            </div>
          );
        })}

        {/* Run output — per output port */}
        {runOutput && runStatus !== 'idle' && runStatus !== 'running' && (
          <div style={{ marginTop: 6 }}>
            {runStatus === 'error' ? (
              <div style={{
                background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: 4, overflow: 'hidden',
              }}>
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
            ) : outputPorts.length > 0 ? (
              outputPorts.map((p) => {
                const portValue = runOutput?.[p.key];
                const hasValue = portValue !== undefined && portValue !== null;
                const displayValue = hasValue ? portValue : (outputPorts.length === 1 ? runOutput : undefined);
                const hasDisplay = displayValue !== undefined && displayValue !== null;

                return (
                  <div key={p.key} style={{ marginBottom: 4, background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 4, overflow: 'hidden' }}>
                    <div style={{ padding: '3px 6px', fontWeight: 600, fontSize: 10, color: '#389e0d', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: PORT_COLORS[p.type] || '#52c41a', display: 'inline-block' }} />
                      {p.label}
                      {hasDisplay ? ' ✅' : ''}
                    </div>
                    {hasDisplay && (
                      <div style={{ padding: '4px 6px', maxHeight: 120, overflowY: 'auto', fontSize: 9, borderTop: '1px solid #b7eb8f' }}>
                        {p.type === 'table-data' && displayValue?.columns ? (
                          <Suspense fallback={<pre style={{ margin: 0 }}>{JSON.stringify(displayValue, null, 2).slice(0, 80)}...</pre>}>
                            <ExcelRenderer data={displayValue} columnFilter={(data.columnFilter as string[]) || []} rowFilter={(data.rowFilter as string[]) || []} />
                          </Suspense>
                        ) : p.type === 'json-data' ? (
                          <Suspense fallback={<pre style={{ margin: 0 }}>{JSON.stringify(displayValue, null, 2).slice(0, 80)}...</pre>}>
                            <JsonRenderer data={displayValue} />
                          </Suspense>
                        ) : p.type === 'text' && typeof displayValue === 'object' && displayValue?.content ? (
                          <Suspense fallback={<pre style={{ margin: 0 }}>{displayValue.content?.slice(0, 80)}...</pre>}>
                            <LuaRenderer content={displayValue.content} functionName={displayValue.functionName} functionContent={displayValue.functionContent} />
                          </Suspense>
                        ) : typeof displayValue === 'string' ? (
                          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                            {displayValue}
                          </pre>
                        ) : (
                          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                            {JSON.stringify(displayValue, null, 2)}
                          </pre>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            ) : (
              <div style={{
                background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 4, overflow: 'hidden',
              }}>
                <div style={{ padding: '3px 6px', fontWeight: 600, fontSize: 10, color: '#389e0d' }}>✅ 结果</div>
                <div style={{ padding: '4px 6px', maxHeight: 120, overflowY: 'auto', fontSize: 9, borderTop: '1px solid #b7eb8f' }}>
                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                    {typeof runOutput === 'string' ? runOutput : runOutput.fileContent || JSON.stringify(runOutput, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>

      {/* NodeDetailModal */}
      <NodeDetailModal
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        nodeId={id}
        nodeType={nodeType}
        icon={icon}
        label={label}
        fields={fields}
      />
    </>
  );
};

export default BaseNode;
