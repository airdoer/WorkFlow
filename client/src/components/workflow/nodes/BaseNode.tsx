import React, { useCallback, useState, useEffect, useRef, lazy, Suspense, useMemo } from 'react';
import { Handle, Position, useReactFlow, useStore } from 'reactflow';
import { Select } from 'antd';
import { PlayCircleOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined, ExpandOutlined } from '@ant-design/icons';
import { FlowApi } from '../services/FlowApi';
import { getNodePorts } from '../PortTypes';
import { useWorkflowContext } from '../WorkflowContext';
import NodeDetailModal from './NodeDetailModal';

// Internal meta keys injected by the backend runtime type system —
// these should never be shown to the user in output display.
const RUNTIME_META_KEYS = new Set(['__runtime_type__', '__value__']);

/** Strip backend runtime meta keys from an output object for display purposes. */
export function stripRuntimeMeta<T>(obj: T): T {
  if (obj === null || obj === undefined || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj;
  const entries = Object.entries(obj as Record<string, unknown>)
    .filter(([k]) => !RUNTIME_META_KEYS.has(k));
  return Object.fromEntries(entries) as T;
}

// Lazy load renderers to reduce initial bundle
const ExcelRenderer = lazy(() => import('./Excel/UniverRenderer'));
const JsonRenderer = lazy(() => import('./Json/JsonRenderer'));

// Detect binary content (e.g. Excel latin-1 encoded bytes)
function isBinaryContent(str: string): boolean {
  if (str.length < 20) return false;
  let nonPrintable = 0;
  const sample = str.slice(0, 500);
  for (let i = 0; i < sample.length; i++) {
    const code = sample.charCodeAt(i);
    if (code < 32 && code !== 9 && code !== 10 && code !== 13) nonPrintable++;
    else if (code > 126 && code < 160) nonPrintable++;
  }
  return nonPrintable / sample.length > 0.1;
}
const LuaRenderer = lazy(() => import('./Lua/LuaRenderer'));

export type RunStatus = 'idle' | 'running' | 'success' | 'error';
export { FieldTextInput, FieldTextarea };
export interface NodeField {
  key: string;
  label: string;
  placeholder?: string;
  type?: 'text' | 'textarea' | 'number' | 'select' | 'multiselect';
  rows?: number;
  step?: number;
  options?: { label: string; value: string }[];
  /** Dynamic options factory: called with current nodeData at render time.
   *  Takes priority over static `options` when provided.
   */
  optionsFn?: (nodeData: Record<string, any>) => { label: string; value: string }[];
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
  /** Optional React node rendered after the fields area (e.g. table preview) */
  extraContentAfterFields?: React.ReactNode;
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
  'list': '#36cfc9',
  'object': '#fa541c',
};

/* ── Uncontrolled text inputs: DOM is source of truth → cursor never jumps ── */
interface FieldInputProps {
  value: string;
  disabled?: boolean;
  placeholder?: string;
  required?: boolean;
  style?: React.CSSProperties;
  lockedStyle?: React.CSSProperties;
  locked?: boolean;
  onChange: (v: string) => void;
}

const FieldTextInput: React.FC<FieldInputProps> = ({ value, disabled, placeholder, required, style, lockedStyle, locked, onChange }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const prevExternal = useRef(value);

  // Sync external value changes directly to DOM (bypass React controlled input)
  useEffect(() => {
    if (value !== prevExternal.current && inputRef.current) {
      prevExternal.current = value;
      inputRef.current.value = value ?? '';
    }
  }, [value]);

  return (
    <input
      ref={inputRef}
      className="nodrag"
      type="text"
      defaultValue={value ?? ''}
      disabled={disabled}
      placeholder={placeholder}
      onBlur={() => {
        const v = inputRef.current?.value ?? '';
        prevExternal.current = v;
        onChange(v);
      }}
      style={locked ? lockedStyle : style}
    />
  );
};

const FieldTextarea: React.FC<FieldInputProps & { rows?: number }> = ({ value, disabled, placeholder, required, style, lockedStyle, locked, onChange, rows }) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const prevExternal = useRef(value);

  useEffect(() => {
    if (value !== prevExternal.current && textareaRef.current) {
      prevExternal.current = value;
      textareaRef.current.value = value ?? '';
    }
  }, [value]);

  return (
    <textarea
      ref={textareaRef}
      className="nodrag"
      defaultValue={value ?? ''}
      disabled={disabled}
      placeholder={placeholder}
      rows={rows || 3}
      onBlur={() => {
        const v = textareaRef.current?.value ?? '';
        prevExternal.current = v;
        onChange(v);
      }}
      style={locked ? { ...(lockedStyle || {}), resize: 'vertical' } : { ...(style || {}), resize: 'vertical' }}
    />
  );
};

const BaseNode: React.FC<BaseNodeProps> = ({
  data,
  id,
  selected,
  icon,
  label,
  nodeType,
  fields,
  extraContentAfterFields,
}) => {
  const { setNodes, getNodes } = useReactFlow();
  const { workflowId, onNodeUpdate, ensureSaved, multiSelectedIds, compactMode, detailNodeId, setDetailNodeId, getRunStatus, getRunOutput } = useWorkflowContext();
  const detailOpen = detailNodeId === id;

  // Read run status/output from the external store (not from node.data)
  // This keeps node.data small and prevents expensive re-renders
  const runStatus = (getRunStatus(id) as RunStatus) || (data._runStatusHint as RunStatus) || 'idle';
  const runOutput = getRunOutput(id);
  const statusCfg = STATUS_CONFIG[runStatus];

  // Whether this node is part of a multi-selection
  const isMultiSelected = selected && multiSelectedIds.size > 0 && multiSelectedIds.has(id);

  // Reactively track which input ports are connected via edges
  // Use a ref to cache the previous result so the selector returns a stable
  // reference when the connected ports haven't actually changed — this prevents
  // Zustand from triggering a re-render on every store update (e.g. node position).
  const prevPortsRef = useRef<Record<string, boolean>>({});
  const connectedInputPorts = useStore(
    useCallback(
      (s) => {
        const result: Record<string, boolean> = {};
        for (const e of s.edges) {
          if (e.target === id && e.targetHandle) {
            result[e.targetHandle] = true;
          }
        }
        // Compare with previous — return same reference if unchanged
        const prev = prevPortsRef.current;
        const prevKeys = Object.keys(prev);
        const nextKeys = Object.keys(result);
        if (prevKeys.length === nextKeys.length && prevKeys.every(k => result[k] === prev[k])) {
          return prev;
        }
        prevPortsRef.current = result;
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

      // Mark this node as running immediately for visual feedback
      // Use lightweight _runStatusHint instead of full _runStatus + _runOutput
      setNodes((nds) =>
        nds.map((n) =>
          n.id === id ? { ...n, data: { ...n.data, _runStatusHint: 'running' } } : n,
        ),
      );

      // Build clean field config for the current node (latest values, may not be saved yet)
      const cleanConfig: Record<string, any> = {};
      for (const f of fields) {
        if (data[f.key] !== undefined && data[f.key] !== null && String(data[f.key]).trim() !== '') {
          cleanConfig[f.key] = data[f.key];
        }
      }

      // Collect all other nodes' last known runOutput from the external store
      const allNodes = getNodes();
      const nodeDataOverrides: Record<string, any> = {};
      nodeDataOverrides[id] = cleanConfig;
      for (const n of allNodes) {
        if (n.id !== id) {
          const nodeOutput = getRunOutput(n.id);
          if (nodeOutput && !nodeOutput.error) {
            nodeDataOverrides[n.id] = nodeOutput;
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
    [id, nodeType, data, fields, setNodes, canRun, ensureSaved, onNodeUpdate, getNodes, getRunOutput],
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
            onClick={(e) => { e.stopPropagation(); setDetailNodeId(id); }}
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
          // Resolve options: dynamic fn takes priority over static array
          // Merge _runOutput from external store so optionsFn can read it
          const enrichedData = { ...(data as Record<string, any>), _runOutput: runOutput };
          const resolvedOptions = f.optionsFn ? f.optionsFn(enrichedData) : (f.options ?? []);

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
            const textareaStyle = {
              width: '100%', fontSize: 11, padding: '3px 6px',
              border: `1px solid ${f.required && !val ? '#ffccc7' : '#d9d9d9'}`,
              borderRadius: 3, boxSizing: 'border-box' as const,
            };
            return (
              <div key={f.key} style={{ marginBottom: 6 }}>
                {fieldLabel}
                <FieldTextarea
                  value={String(val ?? '')}
                  disabled={locked}
                  locked={locked}
                  placeholder={locked ? '由连线提供' : f.placeholder}
                  rows={f.rows || 3}
                  required={f.required}
                  style={textareaStyle}
                  lockedStyle={{ ...lockedStyle, resize: 'vertical' }}
                  onChange={(v) => !locked && handleFieldChange(f.key, v)}
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

          if (f.type === 'select' && (resolvedOptions.length >= 0 || f.options !== undefined || f.optionsFn !== undefined)) {
            return (
              <div key={f.key} style={{ marginBottom: 6 }}>
                {fieldLabel}
                <div
                  className="nodrag nopan nowheel"
                  onWheel={(e) => e.stopPropagation()}
                >
                  <Select
                    size="small"
                    disabled={locked}
                    value={val || undefined}
                    onChange={(v) => !locked && handleFieldChange(f.key, v)}
                    options={resolvedOptions}
                    placeholder={resolvedOptions.length === 0 ? '运行后加载选项' : (f.placeholder || '选择...')}
                    style={{ width: '100%', fontSize: 11 }}
                    allowClear
                    getPopupContainer={(node) => node.parentElement || document.body}
                    styles={{ popup: { root: { fontSize: 11 } } }}
                  />
                </div>
              </div>
            );
          }

          if (f.type === 'multiselect' && (resolvedOptions.length >= 0 || f.options !== undefined || f.optionsFn !== undefined)) {
            const selectedVals: string[] = Array.isArray(val) ? val : [];
            return (
              <div key={f.key} style={{ marginBottom: 6 }}>
                {fieldLabel}
                <div
                  className="nodrag nopan nowheel"
                  onWheel={(e) => e.stopPropagation()}
                >
                  <Select
                    mode="multiple"
                    size="small"
                    disabled={locked}
                    value={selectedVals}
                    onChange={(v) => !locked && handleFieldChange(f.key, v)}
                    options={resolvedOptions}
                    placeholder={resolvedOptions.length === 0 ? '运行后加载选项' : (f.placeholder || '选择...')}
                    style={{ width: '100%', fontSize: 11 }}
                    maxTagCount={2}
                    maxTagTextLength={8}
                    allowClear
                    getPopupContainer={(node) => node.parentElement || document.body}
                    styles={{ popup: { root: { fontSize: 11 } } }}
                  />
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
          const textInputStyle = {
            width: '100%', fontSize: 11, padding: '3px 6px',
            border: `1px solid ${f.required && !val ? '#ffccc7' : '#d9d9d9'}`,
            borderRadius: 3, boxSizing: 'border-box' as const,
          };
          return (
            <div key={f.key} style={{ marginBottom: 6 }}>
              {fieldLabel}
              <FieldTextInput
                value={String(val ?? '')}
                disabled={locked}
                locked={locked}
                placeholder={locked ? '由连线提供' : f.placeholder}
                required={f.required}
                style={textInputStyle}
                lockedStyle={lockedStyle}
                onChange={(v) => !locked && handleFieldChange(f.key, v)}
              />
            </div>
          );
        })}

        {/* Extra content (e.g. table preview for Excel node) */}
        {extraContentAfterFields && (
          <div style={{ marginTop: 4 }}>{extraContentAfterFields}</div>
        )}

        {/* Run output — per output port */}
        {runOutput && runStatus !== 'idle' && runStatus !== 'running' && (
          compactMode ? (
            /* Compact: only show status badge, no detail content */
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
              <div style={{
                background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: 4, overflow: 'hidden',
              }}>
                <div style={{ padding: '3px 6px', fontWeight: 600, fontSize: 10, color: '#cf1322', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#ff4d4f', display: 'inline-block' }} />
                  错误
                </div>
                <div style={{ padding: '4px 6px', maxHeight: 80, overflowY: 'auto', borderTop: '1px solid #ffccc7', fontSize: 9 }}
                     className="nowheel nopan">
                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: '#cf1322' }}>
                    {typeof runOutput === 'string' ? runOutput : runOutput.error || JSON.stringify(stripRuntimeMeta(runOutput), null, 2)}
                  </pre>
                </div>
              </div>
            ) : outputPorts.length > 0 ? (
              outputPorts.map((p) => {
                const portValue = runOutput?.[p.key];
                const hasValue = portValue !== undefined && portValue !== null;
                const displayValue = hasValue ? portValue : (outputPorts.length === 1 ? stripRuntimeMeta(runOutput) : undefined);
                const hasDisplay = displayValue !== undefined && displayValue !== null;

                // For Excel node: merge allSheets from runOutput into the data prop
                // For Excel node: only merge allSheets when no specific sheetName is selected
                const hasSheetNameSelected = !!(data.sheetName as string);
                const excelDataNode = p.type === 'table-data' && displayValue?.columns && runOutput?.allSheets
                  ? { ...displayValue, activeSheetName: hasSheetNameSelected ? (data.sheetName as string) : undefined, allSheets: hasSheetNameSelected ? undefined : runOutput.allSheets, sheetNames: runOutput.sheetNames }
                  : p.type === 'table-data' && displayValue?.columns ? { ...displayValue, activeSheetName: (data.sheetName as string) || undefined }
                  : displayValue;

                return (
                  <div key={p.key} style={{ marginBottom: 4, background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 4, overflow: 'hidden' }}>
                    <div style={{ padding: '3px 6px', fontWeight: 600, fontSize: 10, color: '#389e0d', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: PORT_COLORS[p.type] || '#52c41a', display: 'inline-block' }} />
                      {p.label}
                      {hasDisplay ? ' ✅' : ''}
                    </div>
                    {hasDisplay && (
                      <div style={{ padding: '4px 6px', maxHeight: 250, overflowY: 'auto', fontSize: 9, borderTop: '1px solid #b7eb8f' }}
                           className="nowheel nopan">
                        {p.type === 'table-data' && displayValue?.columns ? (
                          <Suspense fallback={<pre style={{ margin: 0 }}>{JSON.stringify(excelDataNode, null, 2).slice(0, 80)}...</pre>}>
                            <ExcelRenderer data={excelDataNode} nodeId={id} compact height={220} />
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
                            {isBinaryContent(displayValue) ? '📦 二进制文件' : displayValue}
                          </pre>
                        ) : (
                          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                            {(() => {
                              const json = stripRuntimeMeta(displayValue);
                              if (typeof json === 'object' && json?.fileContent && typeof json.fileContent === 'string' && isBinaryContent(json.fileContent)) {
                                const { fileContent, ...rest } = json;
                                return JSON.stringify({ ...rest, fileContent: '📦 二进制文件' }, null, 2);
                              }
                              return JSON.stringify(json, null, 2);
                            })()}
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
                    {(() => {
                      const val = typeof runOutput === 'string' ? runOutput : runOutput.fileContent || JSON.stringify(stripRuntimeMeta(runOutput), null, 2);
                      if (typeof val === 'string' && isBinaryContent(val)) return '📦 二进制文件';
                      return val;
                    })()}
                  </pre>
                </div>
              </div>
            )}
          </div>
          ) /* end compactMode ternary */
        )}
      </div>
    </div>

      {/* NodeDetailModal */}
      <NodeDetailModal
        open={detailOpen}
        onClose={() => setDetailNodeId(null)}
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
