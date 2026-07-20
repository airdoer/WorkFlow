import React, { useCallback, useState, useEffect, useRef, lazy, Suspense, useMemo } from 'react';
import { Handle, Position, useReactFlow, useStore } from 'reactflow';
import { Select } from 'antd';
import { PlayCircleOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined, MinusCircleOutlined, ExpandOutlined } from '@ant-design/icons';
import { FlowApi } from '../services/FlowApi';
import { getNodePorts, type PortDefinition } from '../PortTypes';
import { useWorkflowContext } from '../WorkflowContext';
import NodeDetailModal from './NodeDetailModal';

// Internal meta keys injected by the backend runtime type system —
// these should never be shown to the user in output display.
const RUNTIME_META_KEYS = new Set(['__runtime_type__', '__value__', '_pollingStatus']);

/** Strip backend runtime meta keys from an output object for display purposes. */
export function stripRuntimeMeta<T>(obj: T): T {
  if (obj === null || obj === undefined || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj;
  const entries = Object.entries(obj as Record<string, unknown>)
    .filter(([k]) => !RUNTIME_META_KEYS.has(k));
  return Object.fromEntries(entries) as T;
}

// ── Node sequence badge ──────────────────────────────────────────────
// Blue rounded-rect badge for the node's topological sequence number.

/** Format an ISO timestamp into a compact relative time string. */
export function formatLastRunTime(isoStr: string): string {
  try {
    const d = new Date(isoStr);
    const now = Date.now();
    const diffMs = now - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return '刚刚';
    if (diffMin < 60) return `${diffMin}分钟前`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}小时前`;
    const diffDay = Math.floor(diffHr / 24);
    if (diffDay < 30) return `${diffDay}天前`;
    // Beyond 30 days, show the date
    return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
  } catch {
    return '';
  }
}

type SeqBadgeSize = 'sm' | 'lg';
export const SeqBadge: React.FC<{ seq: number; size?: SeqBadgeSize }> = ({ seq, size = 'sm' }) => {
  const isLg = size === 'lg';
  return (
    <span style={{
      fontSize: isLg ? 14 : 11, fontWeight: 700, color: '#fff',
      background: '#1677ff', borderRadius: isLg ? 4 : 3,
      padding: isLg ? '1px 7px' : '0 4px',
      lineHeight: isLg ? '20px' : '16px',
      minWidth: isLg ? 26 : 18, textAlign: 'center', flexShrink: 0,
      position: 'relative', top: isLg ? 0 : -2,
      boxShadow: `0 1px 3px rgba(22,119,255,${isLg ? 0.4 : 0.3})`,
    }}>{seq}</span>
  );
};

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

export type RunStatus = 'idle' | 'running' | 'success' | 'error' | 'stale' | 'skipped';
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
  /** Optional React node rendered before the fields area (e.g. variable list) */
  extraContentBeforeFields?: React.ReactNode;
  /** Optional React node rendered after the fields area (e.g. table preview) */
  extraContentAfterFields?: React.ReactNode;
  /** Optional override for port definitions; takes priority over static getNodePorts(nodeType) */
  overridePorts?: PortDefinition[];
}

const STATUS_CONFIG = {
  idle: { color: '#8c8c8c', bg: '#f5f5f5', icon: PlayCircleOutlined, title: '运行节点' },
  running: { color: '#1890ff', bg: '#e6f7ff', icon: LoadingOutlined, title: '运行中...' },
  success: { color: '#52c41a', bg: '#f6ffed', icon: CheckCircleOutlined, title: '运行成功' },
  error: { color: '#ff4d4f', bg: '#fff2f0', icon: CloseCircleOutlined, title: '运行失败' },
  skipped: { color: '#d9d9d9', bg: '#fafafa', icon: MinusCircleOutlined, title: '已跳过（上游未成功）' },
  stale: { color: '#8c8c8c', bg: '#fafafa', icon: PlayCircleOutlined, title: '参数已修改，需重新运行' },
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
      onInput={() => {
        // Immediately mark as changed (stale) on first keystroke
        // Full value sync still happens on onBlur
        const v = inputRef.current?.value ?? '';
        if (v !== prevExternal.current) {
          prevExternal.current = v;
          onChange(v);
        }
      }}
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
      onInput={() => {
        // Immediately mark as changed (stale) on first keystroke
        const v = textareaRef.current?.value ?? '';
        if (v !== prevExternal.current) {
          prevExternal.current = v;
          onChange(v);
        }
      }}
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
  extraContentBeforeFields,
  extraContentAfterFields,
  overridePorts,
}) => {
  const { setNodes, setEdges, getNodes } = useReactFlow();
  const { workflowId, onNodeUpdate, ensureSaved, multiSelectedIds, compactMode, detailNodeId, setDetailNodeId, getRunStatus, getRunOutput } = useWorkflowContext();
  const detailOpen = detailNodeId === id;

  // Read run status/output from the external store (not from node.data)
  // This keeps node.data small and prevents expensive re-renders
  const runStatus = (getRunStatus(id) as RunStatus) || (data._runStatusHint as RunStatus) || 'idle';
  const runOutput = getRunOutput(id);
  const statusCfg = STATUS_CONFIG[runStatus];

  // Last run result: when stale, _runStatus still holds the original success/error
  const lastRunResult = (data._runStatus as RunStatus) || (runStatus !== 'stale' ? runStatus : 'idle');

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

  // Resolve upstream values for locked (connected) fields
  // Reads from upstream node's CURRENT data (not stale runOutput).
  // Uses useStore selector to stay reactive; caches result to avoid unnecessary re-renders.
  const upstreamValuesCacheRef = useRef<Record<string, any>>({});
  const upstreamValues = useStore(
    useCallback(
      (s) => {
        const result: Record<string, any> = {};
        for (const e of s.edges) {
          if (e.target !== id || !e.targetHandle) continue;
          const srcNode = s.nodeInternals.get(e.source);
          if (!srcNode) continue;
          const srcData = srcNode.data as Record<string, any> | undefined;
          if (!srcData) continue;

          // Priority 1: read current field value from source node data
          // (matches what the upstream node's UI shows right now, even if stale)
          const srcHandle = e.sourceHandle;
          if (srcHandle && srcData[srcHandle] !== undefined && String(srcData[srcHandle]).trim() !== '') {
            result[e.targetHandle] = srcData[srcHandle];
            continue;
          }

          // Priority 2: read from _runOutput (if node hasn't been modified since last run)
          const srcOutput = srcData._runOutput as Record<string, any> | undefined;
          if (!srcOutput) continue;
          if (srcHandle && srcOutput[srcHandle] !== undefined) {
            result[e.targetHandle] = srcOutput[srcHandle];
          } else if (srcOutput.__value__ !== undefined) {
            result[e.targetHandle] = srcOutput.__value__;
          } else {
            for (const [k, v] of Object.entries(srcOutput)) {
              if (!k.startsWith('__') && k !== 'success' && k !== 'error') {
                result[e.targetHandle] = v;
                break;
              }
            }
          }
        }
        // Shallow-equal cache check to return stable reference
        const prev = upstreamValuesCacheRef.current;
        const prevKeys = Object.keys(prev);
        const nextKeys = Object.keys(result);
        if (prevKeys.length === nextKeys.length && prevKeys.every(k => result[k] === prev[k])) {
          return prev;
        }
        upstreamValuesCacheRef.current = result;
        return result;
      },
      [id],
    ),
  );

  const ports = overridePorts || getNodePorts(nodeType);
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
      setNodes((nds) => {
        const updated = nds.map((n) => {
          if (n.id !== id) return n;
          const prevStatus = (n.data as any)._runStatusHint || (n.data as any)._runStatus || 'idle';
          // If node was success/error, mark as stale (parameter changed after run)
          const newHint = (prevStatus === 'success' || prevStatus === 'error') ? 'stale' : prevStatus;
          return { ...n, data: { ...n.data, [key]: value, _runStatusHint: newHint } };
        });

        // If this node became stale, propagate stale to all downstream nodes via edges
        const prevStatus = (nds.find((n) => n.id === id)?.data as any)?._runStatusHint || (nds.find((n) => n.id === id)?.data as any)?._runStatus || 'idle';
        const becameStale = (prevStatus === 'success' || prevStatus === 'error') && value !== (nds.find((n) => n.id === id)?.data as any)?.[key];
        if (becameStale) {
          // BFS to find all downstream nodes
          const edges = useStore.getState?.()?.edges || [];
          const visited = new Set<string>([id]);
          const queue = [id];
          while (queue.length) {
            const nid = queue.shift()!;
            for (const e of edges) {
              if (e.source === nid && !visited.has(e.target)) {
                visited.add(e.target);
                queue.push(e.target);
              }
            }
          }
          // Mark all downstream nodes as stale
          return updated.map((n) => {
            if (!visited.has(n.id) || n.id === id) return n; // id already handled above
            const s = (n.data as any)._runStatusHint || (n.data as any)._runStatus || 'idle';
            if (s === 'success' || s === 'error') {
              return { ...n, data: { ...n.data, _runStatusHint: 'stale' } };
            }
            return n;
          });
        }
        return updated;
      });

      // Deactivate outgoing edges from the stale node (they may carry old data)
      if (setEdges) {
        setEdges((eds) =>
          eds.map((e) =>
            e.source === id ? { ...e, data: { ...e.data, activated: false } } : e,
          ),
        );
      }
    },
    [id, setNodes, setEdges],
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
          : runStatus === 'stale'
            ? '#bfbfbf'
            : selected
              ? '#1890ff'
              : '#d9d9d9';

  const headerBg =
    runStatus === 'success'
      ? '#f6ffed'
      : runStatus === 'error'
        ? '#fff2f0'
        : runStatus === 'running'
          ? '#e6f7ff'
          : runStatus === 'stale'
            ? '#f5f5f5'
            : 'transparent';

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
        width: 280,
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
          background: headerBg,
          borderRadius: '6px 6px 0 0',
        }}
      >
        <div style={{ fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 4 }}>
          {(data as any)._seq != null && <SeqBadge seq={(data as any)._seq} />}
          <span style={{ fontSize: 16 }}>{icon}</span>
          <span>{label}</span>
        </div>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {/* Last run time badge */}
          {(data as any)._lastRunTime && (runStatus === 'success' || runStatus === 'error' || runStatus === 'stale' || runStatus === 'running') && (
            <span
              title={`最后运行: ${new Date((data as any)._lastRunTime).toLocaleString('zh-CN')}`}
              style={{
                fontSize: 9,
                color: lastRunResult === 'success' ? '#52c41a' : lastRunResult === 'error' ? '#cf1322' : '#999',
                background: lastRunResult === 'success' ? '#f6ffed' : lastRunResult === 'error' ? '#fff2f0' : '#f5f5f5',
                border: `1px solid ${lastRunResult === 'success' ? '#b7eb8f' : lastRunResult === 'error' ? '#ffccc7' : '#e8e8e8'}`,
                borderRadius: 3,
                padding: '1px 4px',
                lineHeight: '14px',
                whiteSpace: 'nowrap',
              }}
            >
              {formatLastRunTime((data as any)._lastRunTime)}
            </span>
          )}
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
            <span style={canRun && runStatus === 'running' ? { display: 'inline-flex', animation: 'wf-btn-spin 1s linear infinite' } : undefined}>
              {React.createElement(canRun ? statusCfg.icon : PlayCircleOutlined, { spin: canRun && runStatus === 'running' })}
            </span>
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
                    cursor: 'crosshair',
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
                    cursor: 'move',
                  }}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ===== Section 3: Content — fields + output ===== */}
      <div style={{ padding: '8px 10px' }}>
        {extraContentBeforeFields && (
          <div style={{ marginBottom: 6 }}>{extraContentBeforeFields}</div>
        )}
        {fields.map((f) => {
          const locked = !!(f.linkedPortKey && connectedInputPorts[f.linkedPortKey]);
          // When locked (connected), show upstream value instead of stale local data
          const upstreamVal = f.linkedPortKey ? upstreamValues[f.linkedPortKey] : undefined;
          const val = locked && upstreamVal !== undefined
            ? upstreamVal
            : (data[f.key] as any) ?? (f.type === 'multiselect' ? [] : '');
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
                    showSearch
                    optionFilterProp="label"
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
                    showSearch
                    optionFilterProp="label"
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
        {runOutput && runStatus !== 'idle' && (runStatus !== 'running' || runOutput?._pollingStatus === 'polling') && (
          compactMode ? (
            /* Compact: only show status badge, no detail content */
            <div style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 4, fontSize: 10 }}>
              {runStatus === 'error' ? (
                <span style={{ color: '#cf1322' }}>❌ 错误</span>
              ) : runOutput?._pollingStatus === 'polling' ? (
                <span style={{ color: '#096dd9' }}>⏳ 执行中</span>
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
            ) : runOutput?._pollingStatus === 'polling' ? (
              /* ── Seal 轮询中间状态：蓝色主题 ── */
              <div style={{
                background: '#e6f7ff', border: '1px solid #91d5ff', borderRadius: 4, overflow: 'hidden',
              }}>
                <div style={{ padding: '3px 6px', fontWeight: 600, fontSize: 10, color: '#096dd9', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#1890ff', display: 'inline-block', animation: 'seal-pulse 1.5s infinite' }} />
                  任务执行中（轮询等待）
                </div>
                <div style={{ padding: '4px 6px', maxHeight: 200, overflowY: 'auto', fontSize: 9, borderTop: '1px solid #91d5ff' }}
                     className="nowheel nopan">
                  {outputPorts.length > 0 ? outputPorts.map((p) => {
                    const portValue = runOutput?.[p.key];
                    const hasValue = portValue !== undefined && portValue !== null;
                    const displayValue = hasValue ? portValue : undefined;
                    const hasDisplay = displayValue !== undefined && displayValue !== null;
                    return (
                      <div key={p.key} style={{ marginBottom: 2, display: 'flex', alignItems: 'baseline', gap: 4 }}>
                        <span style={{ color: '#096dd9', fontWeight: 600, fontSize: 9, minWidth: 60, textAlign: 'right' }}>{p.label}:</span>
                        {p.key === 'executionSuccess' && !hasDisplay ? (
                          <span style={{ color: '#8c8c8c', fontSize: 9 }}>⏳ 等待中...</span>
                        ) : hasDisplay && p.key === 'taskUrl' && typeof displayValue === 'string' && /^https?:\/\//i.test(displayValue) ? (
                          <a href={displayValue} target="_blank" rel="noopener noreferrer"
                             style={{ color: '#1890ff', textDecoration: 'underline', fontSize: 9 }}>🔗 查看任务</a>
                        ) : hasDisplay && typeof displayValue === 'boolean' ? (
                          <span style={{ fontSize: 9, color: displayValue ? '#389e0d' : '#cf1322' }}>{displayValue ? '✅ true' : '❌ false'}</span>
                        ) : hasDisplay ? (
                          <span style={{ fontSize: 9 }}>{String(displayValue)}</span>
                        ) : (
                          <span style={{ color: '#8c8c8c', fontSize: 9 }}>-</span>
                        )}
                      </div>
                    );
                  }) : (
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{JSON.stringify(stripRuntimeMeta(runOutput), null, 2)}</pre>
                  )}
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
                          isBinaryContent(displayValue) ? (
                            <pre style={{ margin: 0 }}>📦 二进制文件</pre>
                          ) : /^https?:\/\//i.test(displayValue) ? (
                            <a href={displayValue} target="_blank" rel="noopener noreferrer"
                               style={{ color: '#1890ff', textDecoration: 'underline', fontSize: 10, wordBreak: 'break-all' }}>
                              {p.key === 'taskUrl' || p.label === '任务链接' ? `🔗 查看任务` : displayValue}
                            </a>
                          ) : (
                            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{displayValue}</pre>
                          )
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
