import React, { useCallback, useState, useMemo, lazy, Suspense, useRef } from 'react';
import { Modal, Button, Tag, message, Select } from 'antd';
import { PlayCircleOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined, CopyOutlined, CloseOutlined } from '@ant-design/icons';
import { useReactFlow, useStore } from 'reactflow';
import type { NodeField, RunStatus } from './BaseNode';
import { FieldTextInput, FieldTextarea, stripRuntimeMeta, SeqBadge } from './BaseNode';
import { getNodePorts } from '../PortTypes';
import { FlowApi } from '../services/FlowApi';
import { useWorkflowContext } from '../WorkflowContext';
import { PanelSection } from '../PanelSection';
import { MiniTable } from './Table/index';
import type { TableData } from './Table/index';

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

const STATUS_CONFIG: Record<RunStatus, { color: string; bg: string; label: string; icon: any }> = {
  idle: { color: '#8c8c8c', bg: '#e8e8e8', label: '未运行', icon: PlayCircleOutlined },
  running: { color: '#1890ff', bg: '#bae7ff', label: '运行中', icon: LoadingOutlined },
  success: { color: '#52c41a', bg: '#d9f7be', label: '运行成功', icon: CheckCircleOutlined },
  error: { color: '#ff4d4f', bg: '#ffa39e', label: '运行失败', icon: CloseCircleOutlined },
};

// Lazy renderers
const ExcelRenderer = lazy(() => import('./Excel/UniverRenderer'));
const JsonRenderer = lazy(() => import('./Json/JsonRenderer'));
const LuaRenderer = lazy(() => import('./Lua/LuaRenderer'));
const DiffRenderer = lazy(() => import('./Diff/DiffRenderer'));

interface NodeDetailModalProps {
  open: boolean;
  onClose: () => void;
  nodeId: string;
  nodeType: string;
  icon: string;
  label: string;
  fields: NodeField[];
}

/** Collapsible section — 已迁移到 PanelSection，此函数保留为别名 */
const DetailSection = ({
  title, defaultOpen = true, children, extra,
}: {
  title: string; children: React.ReactNode; defaultOpen?: boolean; extra?: React.ReactNode;
}) => (
  <PanelSection title={title} defaultOpen={defaultOpen} extra={extra}>
    {children}
  </PanelSection>
);

const NodeDetailModal: React.FC<NodeDetailModalProps> = ({
  open, onClose, nodeId, nodeType, icon, label, fields,
}) => {
  const [closeHovered, setCloseHovered] = React.useState(false);
  const { setNodes, getEdges, getNodes } = useReactFlow();
  const { workflowId, onNodeUpdate, getRunStatus, getRunOutput } = useWorkflowContext();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Subscribe to live node data via useStore so any setNodes update re-renders this component
  const nodeData = useStore(
    useCallback(
      (s) => {
        const n = s.nodeInternals.get(nodeId);
        return (n?.data || {}) as Record<string, any>;
      },
      [nodeId],
    ),
  );

  const data = nodeData;
  // Read run status/output from the external store (lightweight, doesn't bloat node.data)
  const runStatus: RunStatus = (getRunStatus(nodeId) as RunStatus) || (data._runStatusHint as RunStatus) || 'idle';
  const runOutput = getRunOutput(nodeId);
  const statusCfg = STATUS_CONFIG[runStatus];

  const ports = getNodePorts(nodeType);
  const inputPorts = ports.filter((p) => p.direction === 'input');
  const outputPorts = ports.filter((p) => p.direction === 'output');

  // Subscribe to all nodes so upstream data changes also trigger re-render
  // Only subscribe when modal is open to avoid unnecessary re-renders when closed
  const allNodes = useStore(
    useCallback(
      (s) => {
        if (!open) return [] as any[];
        return Array.from(s.nodeInternals.values());
      },
      [open],
    ),
  );

  // Subscribe to edges reactively so linkedPortKey checks update in real-time
  // Only subscribe when modal is open
  const allEdges = useStore(
    useCallback(
      (s) => {
        if (!open) return [] as any[];
        return s.edges;
      },
      [open],
    ),
  );

  /**
   * Map of portKey -> true when that input port has an active connected edge.
   * Used to lock fields whose linkedPortKey is connected.
   */
  const connectedInputPorts = useMemo(() => {
    const result: Record<string, boolean> = {};
    for (const edge of allEdges) {
      if (edge.target === nodeId && edge.targetHandle) {
        result[edge.targetHandle] = true;
      }
    }
    return result;
  }, [allEdges, nodeId]);

  /** Whether a field's linked port is currently wired */
  const isFieldLocked = useCallback(
    (f: { linkedPortKey?: string }) => !!f.linkedPortKey && !!connectedInputPorts[f.linkedPortKey],
    [connectedInputPorts],
  );

  // Upstream data
  // Detect binary content (e.g. Excel latin-1 encoded bytes)
  const isBinaryContent = (str: string): boolean => {
    if (str.length < 20) return false;
    let nonPrintable = 0;
    const sample = str.slice(0, 500);
    for (let i = 0; i < sample.length; i++) {
      const code = sample.charCodeAt(i);
      if (code < 32 && code !== 9 && code !== 10 && code !== 13) nonPrintable++;
      else if (code > 126 && code < 160) nonPrintable++;
    }
    return nonPrintable / sample.length > 0.1;
  };

  const formatPreviewValue = (value: any): string | null => {
    if (value === undefined || value === null) return null;
    if (typeof value === 'string') {
      return isBinaryContent(value) ? '📦 二进制文件，不支持文本预览' : value;
    }
    if (typeof value === 'object' && value?.fileContent && typeof value.fileContent === 'string' && isBinaryContent(value.fileContent)) {
      const { fileContent, ...rest } = value;
      return JSON.stringify({ ...rest, fileContent: '📦 二进制文件，不支持文本预览' }, null, 2);
    }
    return JSON.stringify(value, null, 2);
  };

  const upstreamInfo = useMemo(() => {
    const edges = getEdges();
    const incoming = edges.filter((e) => e.target === nodeId && e.data?.matchStatus === 'matched');
    return incoming.map((e) => {
      const tgtPort = inputPorts.find((p) => p.key === e.targetHandle);
      // Read upstream output from external store (lightweight)
      const srcOutput = getRunOutput(e.source);
      let previewValue: any = undefined;
      if (srcOutput && !srcOutput.error) {
        if (e.sourceHandle && srcOutput[e.sourceHandle] !== undefined) {
          previewValue = srcOutput[e.sourceHandle];
        } else {
          previewValue = srcOutput;
        }
      }
      return {
        sourceId: e.source,
        srcHandle: e.sourceHandle,
        tgtHandle: e.targetHandle,
        tgtPortLabel: tgtPort?.label || e.targetHandle || '',
        tgtPortType: tgtPort?.type || '',
        hasData: previewValue !== undefined,
        preview: formatPreviewValue(previewValue),
        isBinary: typeof previewValue === 'string' ? isBinaryContent(previewValue) : (!!(typeof previewValue === 'object' && previewValue?.fileContent && typeof previewValue.fileContent === 'string' && isBinaryContent(previewValue.fileContent))),
      };
    });
  }, [getEdges, getRunOutput, nodeId, inputPorts]);

  // Check required fields — a required field is satisfied if it has a value OR its linked port is connected
  const canRun = useMemo(() => {
    if (runStatus === 'running') return false;
    return fields
      .filter((f) => f.required)
      .every((f) => {
        if (isFieldLocked(f)) return true; // connected via wire → always satisfied
        const val = data[f.key];
        if (f.type === 'multiselect') return Array.isArray(val) && val.length > 0;
        return val !== undefined && val !== null && String(val).trim() !== '';
      });
  }, [fields, data, runStatus, isFieldLocked]);

  const missingRequired = useMemo(
    () => fields.filter((f) => f.required && !data[f.key] && !isFieldLocked(f)),
    [fields, data, isFieldLocked],
  );

  const handleFieldChange = useCallback(
    (key: string, value: any) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId ? { ...n, data: { ...n.data, [key]: value } } : n,
        ),
      );
    },
    [nodeId, setNodes],
  );

  const handleRun = useCallback(async () => {
    if (!canRun) return;

    if (!workflowId) {
      console.warn('[NodeDetailModal] No workflowId, cannot run via WebSocket');
      return;
    }

    // Mark this node as running immediately for visual feedback
    // Use lightweight _runStatusHint instead of full _runStatus + _runOutput
    setNodes((nds) =>
      nds.map((n) =>
        n.id === nodeId ? { ...n, data: { ...n.data, _runStatusHint: 'running' } } : n,
      ),
    );

    // Build clean config for the current node
    const cleanConfig: Record<string, any> = {};
    for (const f of fields) {
      if (data[f.key] !== undefined && data[f.key] !== null && String(data[f.key]).trim() !== '') {
        cleanConfig[f.key] = data[f.key];
      }
    }

    // Collect all other nodes' last known runOutput from the external store
    const allNodesLocal = getNodes();
    const nodeDataOverrides: Record<string, any> = {};
    nodeDataOverrides[nodeId] = cleanConfig;
    for (const n of allNodesLocal) {
      if (n.id !== nodeId) {
        const nodeOutput = getRunOutput(n.id);
        if (nodeOutput && !nodeOutput.error) {
          nodeDataOverrides[n.id] = nodeOutput;
        }
      }
    }

    FlowApi.runNodeWS(
      workflowId,
      nodeId,
      nodeDataOverrides,
      onNodeUpdate,
      (_status, error) => {
        if (error) console.error('[NodeDetailModal] NodeRun error:', error);
      },
    );
  }, [nodeId, data, fields, setNodes, canRun, workflowId, onNodeUpdate, getNodes, getRunOutput]);

  const copyToClipboard = useCallback((text: string) => {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => message.success('已复制'));
    } else {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      message.success('已复制');
    }
  }, []);

  const outputText = useMemo(() => {
    if (!runOutput) return '';
    if (typeof runOutput === 'string') return isBinaryContent(runOutput) ? '📦 二进制文件，不支持文本预览' : runOutput;
    if (runOutput.error) return runOutput.error;
    // For Excel output with binary fileContent, strip it for display
    if (typeof runOutput === 'object' && runOutput?.fileContent && typeof runOutput.fileContent === 'string' && isBinaryContent(runOutput.fileContent)) {
      const { fileContent, ...rest } = runOutput;
      return JSON.stringify({ ...rest, fileContent: '📦 二进制文件' }, null, 2);
    }
    return JSON.stringify(stripRuntimeMeta(runOutput), null, 2);
  }, [runOutput]);

  if (!open) return null;

  return (
    <Modal
      title={null}
      open={open}
      onCancel={onClose}
      width="80vw"
      style={{ top: 20 }}
      closeIcon={
        <span
          onMouseEnter={() => setCloseHovered(true)}
          onMouseLeave={() => setCloseHovered(false)}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 64,
            height: 32,
            borderRadius: 6,
            background: closeHovered ? '#595959' : '#8c8c8c',
            color: '#fff',
            fontSize: 14,
            boxShadow: '0 2px 6px rgba(0,0,0,0.2)',
            transition: 'background 0.2s',
          }}
        >
          <CloseOutlined />
        </span>
      }
      styles={{ body: { padding: 0, height: '80vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' } }}
      footer={[
        <Button key="copy" icon={<CopyOutlined />} onClick={() => copyToClipboard(outputText)} disabled={!outputText}>
          复制输出
        </Button>,
        <Button key="close" type="primary" onClick={onClose}>
          关闭
        </Button>,
      ]}
    >
      {/* ===== Sticky zone: Node type header + Parameters ===== */}
      <div style={{ flexShrink: 0, borderBottom: '2px solid #d9d9d9', background: '#fff' }}>
        {/* Node type header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 16px', background: statusCfg.bg,
          borderBottom: `2px solid ${runStatus === 'error' ? '#ffccc7' : runStatus === 'success' ? '#b7eb8f' : '#e8e8e8'}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {(data._seq != null) && <SeqBadge seq={data._seq as number} size="lg" />}
            <span style={{ fontSize: 22 }}>{icon}</span>
            <span style={{ fontWeight: 700, fontSize: 18, color: '#333' }}>{label}</span>
            <Tag color={runStatus === 'success' ? 'green' : runStatus === 'error' ? 'red' : runStatus === 'running' ? 'blue' : 'default'} style={{ fontSize: 12 }}>
              {React.createElement(statusCfg.icon, { spin: runStatus === 'running' })}
              <span style={{ marginLeft: 4 }}>{statusCfg.label}</span>
            </Tag>
          </div>
          <Button
            type="primary"
            icon={React.createElement(canRun ? (runStatus === 'running' ? LoadingOutlined : PlayCircleOutlined) : PlayCircleOutlined, { spin: runStatus === 'running' })}
            onClick={handleRun}
            disabled={!canRun}
            title={!canRun ? `请填写必填项: ${missingRequired.map((f) => f.label).join(', ')}` : '运行节点'}
            style={{ marginRight: 15 }}
          >
            运行
          </Button>
        </div>

        {/* Parameters — full-width stacked fields, collapsible but fixed at top */}
        <DetailSection title="参数" defaultOpen extra={<span style={{ fontSize: 11, color: '#666' }}>{fields.length} 项</span>}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {fields.map((f) => {
              const locked = isFieldLocked(f);
              const val = (data[f.key] as any) ?? (f.type === 'multiselect' ? [] : '');
              // Resolve options: dynamic fn takes priority over static array
              const resolvedOptions = f.optionsFn ? f.optionsFn(data as Record<string, any>) : (f.options ?? []);

              // Shared label with locked indicator
              const fieldLabel = (
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#555', marginBottom: 4 }}>
                  {f.label}
                  {f.required && !locked && <span style={{ color: '#ff4d4f', marginLeft: 4 }}>*</span>}
                  {locked && (
                    <span style={{
                      marginLeft: 8, fontSize: 11, fontWeight: 400,
                      color: '#2f54eb', background: '#f0f5ff', border: '1px solid #adc6ff',
                      borderRadius: 3, padding: '1px 6px',
                    }}>
                      🔗 由连线提供
                    </span>
                  )}
                </label>
              );

              // Shared locked overlay styles
              const lockedInputStyle: React.CSSProperties = {
                width: '100%', fontSize: 13, padding: '8px 12px',
                border: '1px solid #d9d9d9', borderRadius: 4, boxSizing: 'border-box',
                background: '#f5f5f5', color: '#aaa', cursor: 'not-allowed',
              };

              if (f.type === 'textarea') {
                return (
                  <div key={f.key}>
                    {fieldLabel}
                    <FieldTextarea
                      value={String(val ?? '')}
                      disabled={locked}
                      locked={locked}
                      onChange={(v) => !locked && handleFieldChange(f.key, v)}
                      placeholder={locked ? '由连线提供' : f.placeholder}
                      rows={f.rows || 4}
                      style={locked ? { ...lockedInputStyle, resize: 'vertical' } : {
                        width: '100%', fontSize: 13, padding: '8px 12px',
                        border: `1px solid ${f.required && !val ? '#ffccc7' : '#d9d9d9'}`,
                        borderRadius: 4, resize: 'vertical', boxSizing: 'border-box',
                      }}
                    />
                  </div>
                );
              }

              if (f.type === 'number') {
                return (
                  <div key={f.key}>
                    {fieldLabel}
                    <FieldTextInput
                      value={String(val ?? '')}
                      disabled={locked}
                      locked={locked}
                      onChange={(v) => !locked && handleFieldChange(f.key, parseFloat(v) || 0)}
                      placeholder={locked ? '由连线提供' : f.placeholder}
                      style={locked ? lockedInputStyle : {
                        width: '100%', fontSize: 13, padding: '8px 12px',
                        border: `1px solid ${f.required && !val ? '#ffccc7' : '#d9d9d9'}`,
                        borderRadius: 4, boxSizing: 'border-box',
                      }}
                    />
                  </div>
                );
              }

              if (f.type === 'select' && (f.options !== undefined || f.optionsFn !== undefined)) {
                return (
                  <div key={f.key}>
                    {fieldLabel}
                    <Select
                      disabled={locked}
                      value={val || undefined}
                      onChange={(v) => !locked && handleFieldChange(f.key, v)}
                      options={resolvedOptions}
                      placeholder={resolvedOptions.length === 0 ? '运行后加载选项' : (f.placeholder || '选择...')}
                      style={{ width: '100%', fontSize: 13 }}
                      allowClear
                      getPopupContainer={(node) => node.parentElement || document.body}
                    />
                  </div>
                );
              }

              if (f.type === 'multiselect' && (f.options !== undefined || f.optionsFn !== undefined)) {
                const selected: string[] = Array.isArray(val) ? val : [];
                return (
                  <div key={f.key}>
                    {fieldLabel}
                    <Select
                      mode="multiple"
                      disabled={locked}
                      value={selected}
                      onChange={(v) => !locked && handleFieldChange(f.key, v)}
                      options={resolvedOptions}
                      placeholder={resolvedOptions.length === 0 ? '运行后加载选项' : (f.placeholder || '选择...')}
                      style={{ width: '100%', fontSize: 13 }}
                      allowClear
                      getPopupContainer={(node) => node.parentElement || document.body}
                    />
                  </div>
                );
              }

              // Default: text — full width
              return (
                <div key={f.key}>
                  {fieldLabel}
                  <FieldTextInput
                    value={String(val ?? '')}
                    disabled={locked}
                    locked={locked}
                    onChange={(v) => !locked && handleFieldChange(f.key, v)}
                    placeholder={locked ? '由连线提供' : f.placeholder}
                    style={locked ? lockedInputStyle : {
                      width: '100%', fontSize: 13, padding: '8px 12px',
                      border: `1px solid ${f.required && !val ? '#ffccc7' : '#d9d9d9'}`,
                      borderRadius: 4, boxSizing: 'border-box',
                    }}
                  />
                </div>
              );
            })}
          </div>
        </DetailSection>
      </div>

      {/* ===== Scrollable zone: Port info, Input content, Output content ===== */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        {/* Section: Port Info */}
        {(inputPorts.length > 0 || outputPorts.length > 0) && (
          <DetailSection title="端口信息" defaultOpen={false} extra={
            <span style={{ fontSize: 11, color: '#666' }}>{inputPorts.length} 入 / {outputPorts.length} 出</span>
          }>
            <div style={{ display: 'flex', gap: 24 }}>
              {inputPorts.length > 0 && (
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 8, color: '#555' }}>输入端口</div>
                  {inputPorts.map((p) => (
                    <div key={p.key} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span style={{ width: 10, height: 10, borderRadius: '50%', background: PORT_COLORS[p.type] || '#d9d9d9', display: 'inline-block', flexShrink: 0 }} />
                      <span style={{ fontSize: 13 }}>{p.label}</span>
                      <Tag style={{ fontSize: 10, margin: 0 }}>{p.type}</Tag>
                    </div>
                  ))}
                </div>
              )}
              {outputPorts.length > 0 && (
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 8, color: '#555' }}>输出端口</div>
                  {outputPorts.map((p) => (
                    <div key={p.key} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span style={{ width: 10, height: 10, borderRadius: '50%', background: PORT_COLORS[p.type] || '#d9d9d9', display: 'inline-block', flexShrink: 0 }} />
                      <span style={{ fontSize: 13 }}>{p.label}</span>
                      <Tag style={{ fontSize: 10, margin: 0 }}>{p.type}</Tag>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </DetailSection>
        )}

        {/* Section: Input Content */}
        {inputPorts.length > 0 && (
          <DetailSection title="输入内容" defaultOpen={upstreamInfo.length > 0} extra={upstreamInfo.length > 0 ? <Tag color="blue">{upstreamInfo.length}</Tag> : undefined}>
            {upstreamInfo.length === 0 ? (
              <div style={{ fontSize: 12, color: '#999' }}>未连接上游节点</div>
            ) : (
              <div style={{ fontSize: 12, color: '#333' }}>
                {upstreamInfo.map((u) => (
                  <div key={u.tgtHandle} style={{ marginBottom: 10, padding: '8px 10px', background: '#f9f9f9', borderRadius: 4, border: '1px solid #e8e8e8' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: PORT_COLORS[u.tgtPortType] || '#d9d9d9', display: 'inline-block' }} />
                      <span style={{ fontWeight: 600, fontSize: 13 }}>{u.tgtPortLabel}</span>
                      {u.hasData ? <Tag color="green" style={{ margin: 0 }}>已接收</Tag> : <Tag color="orange" style={{ margin: 0 }}>未接收</Tag>}
                    </div>
                    <div style={{ fontSize: 11, color: '#888', marginBottom: 6 }}>来自 {u.sourceId} → {u.srcHandle || '全部输出'}</div>
                    {u.hasData && u.preview && !u.isBinary && (
                      <pre style={{
                        margin: 0, padding: '8px 10px', background: '#fff', border: '1px solid #e8e8e8',
                        borderRadius: 4, maxHeight: 200, overflowY: 'auto', fontSize: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                      }}>
                        {u.preview}
                      </pre>
                    )}
                    {u.hasData && u.isBinary && (
                      <div style={{ fontSize: 11, color: '#999', padding: '4px 8px', background: '#fff', border: '1px solid #e8e8e8', borderRadius: 4 }}>
                        📦 二进制文件内容（不可预览）
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </DetailSection>
        )}

        {/* Section: Output Content — structured per output port */}
        {(runStatus === 'success' || runStatus === 'error') && (
          <DetailSection title="输出内容" defaultOpen extra={
            runStatus === 'error' ? <Tag color="red">错误</Tag> : <Tag color="green">成功</Tag>
          }>
            {runStatus === 'error' ? (
              <div style={{ marginBottom: 10, padding: '8px 10px', background: '#fff2f0', borderRadius: 4, border: '1px solid #ffccc7' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ff4d4f', display: 'inline-block' }} />
                  <span style={{ fontWeight: 600, fontSize: 13, color: '#cf1322' }}>错误</span>
                </div>
                <pre style={{ margin: 0, padding: '6px 8px', background: '#fff', border: '1px solid #ffccc7', borderRadius: 4, fontSize: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: '#cf1322' }}>
                  {typeof runOutput === 'string' ? runOutput : runOutput?.error || JSON.stringify(stripRuntimeMeta(runOutput), null, 2)}
                </pre>
              </div>
            ) : outputPorts.length > 0 ? (
              outputPorts.map((p) => {
                const portValue = runOutput?.[p.key];
                const hasValue = portValue !== undefined && portValue !== null;
                // For nodes with a single output port, also check top-level keys if port key not found
                const displayValue = hasValue ? portValue : (outputPorts.length === 1 ? stripRuntimeMeta(runOutput) : undefined);
                const hasDisplay = displayValue !== undefined && displayValue !== null;

                // Determine renderer based on port type
                // Diff node: check if runOutput has contentA + contentB (MUST be checked before isJson)
                const isDiff = nodeType === 'diff' && runOutput?.contentA !== undefined && runOutput?.contentB !== undefined;
                // Table node: 'tables' is an array of {title, columns, rows}
                const isTables = p.key === 'tables' && Array.isArray(displayValue) && displayValue.length > 0 && displayValue[0]?.columns;
                const isExcel = !isTables && p.type === 'table-data' && displayValue?.columns;
                // For Excel node: only merge allSheets when no specific sheetName is selected
                const hasSheetNameSelected = !!(data.sheetName as string);
                const excelData = isExcel && nodeType === 'excel' && runOutput?.allSheets
                  ? { ...displayValue, activeSheetName: hasSheetNameSelected ? (data.sheetName as string) : undefined, allSheets: hasSheetNameSelected ? undefined : runOutput.allSheets, sheetNames: runOutput.sheetNames }
                  : isExcel ? { ...displayValue, activeSheetName: (data.sheetName as string) || undefined }
                  : displayValue;
                const isJson = !isDiff && !isTables && p.type === 'json-data';
                const isLua = p.type === 'text' && typeof displayValue === 'object' && displayValue?.content;
                const isFileContent = !isTables && typeof displayValue === 'string';
                const isPre = !isTables && !isExcel && !isJson && !isLua && !isDiff && typeof displayValue === 'object';

                return (
                  <div key={p.key} style={{ marginBottom: 10, padding: '8px 10px', background: '#f9f9f9', borderRadius: 4, border: '1px solid #e8e8e8' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: PORT_COLORS[p.type] || '#d9d9d9', display: 'inline-block' }} />
                      <span style={{ fontWeight: 600, fontSize: 13 }}>{p.label}</span>
                      {hasDisplay ? <Tag color="green" style={{ margin: 0 }}>有输出</Tag> : <Tag color="orange" style={{ margin: 0 }}>无输出</Tag>}
                      <Tag style={{ fontSize: 10, margin: 0 }}>{p.type}</Tag>
                    </div>
                    {hasDisplay && (
                      <div style={{ background: '#fff', border: '1px solid #e8e8e8', borderRadius: 4, overflow: 'hidden' }}>
                        {isTables ? (
                          <div style={{ padding: '4px 0' }}>
                            {(displayValue as TableData[]).map((t: TableData, i: number) => (
                              <MiniTable key={i} table={t} maxRows={100} />
                            ))}
                          </div>
                        ) : isExcel ? (
                          <Suspense fallback={<pre style={{ margin: 0, padding: 10 }}>{JSON.stringify(excelData, null, 2).slice(0, 200)}...</pre>}>
                            <ExcelRenderer
                              data={excelData}
                              nodeId={nodeId}
                              height={400}
                            />
                          </Suspense>
                        ) : isDiff ? (
                          <Suspense fallback={<div style={{ padding: 20, textAlign: 'center', color: '#999' }}>加载 Diff 编辑器...</div>}>
                            <DiffRenderer
                              original={String(runOutput.contentA ?? '')}
                              modified={String(runOutput.contentB ?? '')}
                              language="plaintext"
                              height={400}
                              showToolbar
                            />
                          </Suspense>
                        ) : isJson ? (
                          <Suspense fallback={<pre style={{ margin: 0, padding: 10 }}>{JSON.stringify(displayValue, null, 2).slice(0, 200)}...</pre>}>
                            <JsonRenderer data={displayValue} />
                          </Suspense>
                        ) : isLua ? (
                          <Suspense fallback={<pre style={{ margin: 0, padding: 10 }}>{displayValue.content?.slice(0, 200)}...</pre>}>
                            <LuaRenderer content={displayValue.content} functionName={displayValue.functionName} functionContent={displayValue.functionContent} />
                          </Suspense>
                        ) : isFileContent ? (
                          <pre style={{ margin: 0, padding: 10, whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontSize: 12 }}>
                            {typeof displayValue === 'string' && isBinaryContent(displayValue) ? '📦 二进制文件，不支持文本预览' : displayValue}
                          </pre>
                        ) : isPre ? (
                          <pre style={{ margin: 0, padding: 10, whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontSize: 12 }}>
                            {(() => {
                              const json = stripRuntimeMeta(displayValue);
                              if (typeof json === 'object' && json?.fileContent && typeof json.fileContent === 'string' && isBinaryContent(json.fileContent)) {
                                const { fileContent, ...rest } = json;
                                return JSON.stringify({ ...rest, fileContent: '📦 二进制文件' }, null, 2);
                              }
                              return JSON.stringify(json, null, 2);
                            })()}
                          </pre>
                        ) : null}
                      </div>
                    )}
                  </div>
                );
              })
            ) : (
              <div style={{ background: '#f9f9f9', border: '1px solid #e8e8e8', borderRadius: 6, overflow: 'hidden', padding: 10 }}>
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontSize: 12 }}>
                  {(() => {
                    const val = typeof runOutput === 'string' ? runOutput : runOutput?.fileContent || JSON.stringify(stripRuntimeMeta(runOutput), null, 2);
                    if (typeof val === 'string' && isBinaryContent(val)) return '📦 二进制文件，不支持文本预览';
                    return val;
                  })()}
                </pre>
              </div>
            )}
          </DetailSection>
        )}
      </div>
    </Modal>
  );
};

export default NodeDetailModal;
