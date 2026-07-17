import React, { useCallback, useState, lazy, Suspense } from 'react';
import type { Node, Edge } from 'reactflow';
import { getNodeRegistry } from './NodeRegistry';
import { Button, Tag, Modal, message, Select } from 'antd';
import { ExpandOutlined, CopyOutlined } from '@ant-design/icons';
import { FlowApi } from './services/FlowApi';
import { useWorkflowContext } from './WorkflowContext';
import type { RunStatus } from './nodes/BaseNode';
import { stripRuntimeMeta, SeqBadge } from './nodes/BaseNode';
import { getNodePorts, type PortDefinition } from './PortTypes';
import { PanelSection } from './PanelSection';
import DiffSummary from './nodes/Diff/DiffSummary';
import { MiniTable } from './nodes/Table/index';
import type { TableData } from './nodes/Table/index';

const DiffRenderer = lazy(() => import('./nodes/Diff/DiffRenderer'));
const UniverRenderer = lazy(() => import('./nodes/Excel/UniverRenderer'));

const PORT_COLORS: Record<string, string> = {
  'file-content': '#1890ff',
  'file-path': '#722ed1',
  'any': '#8c8c8c',
  'text': '#fa8c16',
  'table-data': '#52c41a',
  'json-data': '#13c2c2',
};

/** Section wrapper — 已迁移到 PanelSection，此函数保留为 compact 别名 */
const Section = ({ title, children, defaultOpen = true }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) => (
  <PanelSection title={title} defaultOpen={defaultOpen} compact>
    {children}
  </PanelSection>
);

interface PropertyPanelProps {
  selectedNode: Node | null;
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  edges: Edge[];
  nodes: Node[];
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

const PropertyPanel: React.FC<PropertyPanelProps> = ({ selectedNode, setNodes, edges, nodes, collapsed, onToggleCollapse }) => {
  // ALL hooks must be called before any conditional return
  const [outputModalOpen, setOutputModalOpen] = useState(false);
  const [inputModalOpen, setInputModalOpen] = useState(false);
  const [modalContent, setModalContent] = useState('');
  const [modalTitle, setModalTitle] = useState('');
  const { workflowId, onNodeUpdate, ensureSaved, getRunStatus, getRunOutput } = useWorkflowContext();

  const nodeType = selectedNode?.type ?? '';
  const nodeData = (selectedNode?.data || {}) as Record<string, unknown>;
  const entry = selectedNode ? getNodeRegistry(nodeType) : null;
  const selectedNodeId = selectedNode?.id ?? '';

  // Read run status/output from the external store (lightweight)
  const runStatus = (getRunStatus(selectedNodeId) as RunStatus) || (nodeData._runStatusHint as RunStatus) || 'idle';
  const runOutput = getRunOutput(selectedNodeId);
  const running = runStatus === 'running';

  const ports = getNodePorts(nodeType);
  const inputPorts = ports.filter((p) => p.direction === 'input');
  const outputPorts = ports.filter((p) => p.direction === 'output');

  const incomingEdges = selectedNode ? edges.filter((e) => e.target === selectedNode.id) : [];
  const outgoingEdges = selectedNode ? edges.filter((e) => e.source === selectedNode.id) : [];

  // Collect upstream data per input port — includes actual output preview
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
    return nonPrintable / sample.length > 0.1; // >10% non-printable = binary
  };

  const formatPreviewValue = (value: any): string | null => {
    if (value === undefined || value === null) return null;
    if (typeof value === 'string') {
      return isBinaryContent(value) ? '📦 二进制文件，不支持文本预览' : value;
    }
    // For objects that contain fileContent as a binary string, hide it
    if (typeof value === 'object' && value?.fileContent && typeof value.fileContent === 'string' && isBinaryContent(value.fileContent)) {
      const { fileContent, ...rest } = value;
      return JSON.stringify({ ...rest, fileContent: '📦 二进制文件，不支持文本预览' }, null, 2);
    }
    return JSON.stringify(stripRuntimeMeta(value), null, 2);
  };

  const upstreamData = incomingEdges
    .filter((e) => e.data?.matchStatus === 'matched')
    .map((e) => {
      const srcHandle = e.sourceHandle;
      const tgtHandle = e.targetHandle;
      const tgtPort = inputPorts.find((p) => p.key === tgtHandle);
      // Read upstream node's actual output from external store
      const srcOutput = getRunOutput(e.source);
      // Extract the value for this specific port handle
      let previewValue: any = undefined;
      if (srcOutput && !srcOutput.error) {
        if (srcHandle && srcOutput[srcHandle] !== undefined) {
          previewValue = srcOutput[srcHandle];
        } else {
          // Whole output object
          previewValue = srcOutput;
        }
      }
      return {
        sourceId: e.source,
        srcHandle,
        tgtHandle,
        tgtPortLabel: tgtPort?.label || tgtHandle || '',
        tgtPortType: tgtPort?.type || '',
        hasData: previewValue !== undefined,
        preview: formatPreviewValue(previewValue),
        isBinary: typeof previewValue === 'string' ? isBinaryContent(previewValue) : (!!(typeof previewValue === 'object' && previewValue?.fileContent && typeof previewValue.fileContent === 'string' && isBinaryContent(previewValue.fileContent))),
      };
    });

  const handleFieldChange = useCallback(
    (fieldName: string, value: any) => {
      if (!selectedNode) return;
      setNodes((nds) =>
        nds.map((n) =>
          n.id === selectedNode.id
            ? { ...n, data: { ...n.data, [fieldName]: value } }
            : n,
        ),
      );
    },
    [selectedNode, setNodes],
  );

  const handleRunNode = useCallback(async () => {
    if (!selectedNode) return;

    // Ensure workflow is saved before running
    const savedId = await ensureSaved();
    if (!savedId) return;

    // Mark this node as running immediately for visual feedback
    // Use lightweight _runStatusHint instead of full _runStatus + _runOutput
    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedNode.id
          ? { ...n, data: { ...n.data, _runStatusHint: 'running' } }
          : n,
      ),
    );

    // Build clean config — strip internal state keys
    const cleanConfig: Record<string, any> = {};
    for (const [k, v] of Object.entries(nodeData)) {
      if (!k.startsWith('_') && v !== undefined && v !== null && String(v).trim() !== '') {
        cleanConfig[k] = v;
      }
    }

    // Collect all other nodes' last known runOutput from the external store
    const nodeDataOverrides: Record<string, any> = {};
    nodeDataOverrides[selectedNode.id] = cleanConfig;
    for (const n of nodes) {
      if (n.id !== selectedNode.id) {
        const nodeOutput = getRunOutput(n.id);
        if (nodeOutput && !nodeOutput.error) {
          nodeDataOverrides[n.id] = nodeOutput;
        }
      }
    }

    FlowApi.runNodeWS(
      savedId,
      selectedNode.id,
      nodeDataOverrides,
      onNodeUpdate,
      (_status, error) => {
        if (error) message.error(`运行失败: ${error}`);
      },
    );
  }, [selectedNode, nodeData, nodes, setNodes, ensureSaved, onNodeUpdate, getRunOutput]);

  // Format output for display
  const formatOutput = (output: any): string => {
    if (typeof output === 'string') return isBinaryContent(output) ? '📦 二进制文件，不支持文本预览' : output;
    if (output?.fileContent && typeof output.fileContent === 'string') return isBinaryContent(output.fileContent) ? '📦 二进制文件，不支持文本预览' : output.fileContent;
    if (output?.error) return output.error;
    // For Excel output objects, strip binary fileContent if present
    if (typeof output === 'object' && output?.fileContent && isBinaryContent(output.fileContent)) {
      const { fileContent, ...rest } = output;
      return JSON.stringify({ ...rest, fileContent: '📦 二进制文件' }, null, 2);
    }
    return JSON.stringify(stripRuntimeMeta(output), null, 2);
  };

  const outputText = runOutput ? formatOutput(runOutput) : '';

  // Clipboard helper — navigator.clipboard requires HTTPS, fallback for HTTP (Docker IP)
  const copyToClipboard = useCallback((text: string) => {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => message.success('已复制'));
    } else {
      // Fallback for non-HTTPS contexts
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

  // Now safe to do conditional rendering
  // Collapsed state — show a narrow sidebar strip with expand button
  if (collapsed) {
    return (
      <div
        style={{
          width: 36,
          borderLeft: '1px solid #e8e8e8',
          background: '#fafafa',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          paddingTop: 8,
          gap: 6,
          flexShrink: 0,
        }}
      >
        <button
          onClick={onToggleCollapse}
          title="展开属性面板"
          style={{
            width: 28,
            height: 28,
            borderRadius: 4,
            border: '1px solid #d9d9d9',
            background: '#fff',
            cursor: 'pointer',
            fontSize: 14,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#595959',
          }}
        >
          ◀
        </button>
        <div style={{ writingMode: 'vertical-rl', fontSize: 11, color: '#999', letterSpacing: 2, marginTop: 8 }}>
          属性
        </div>
      </div>
    );
  }

  if (!selectedNode) {
    return (
      <div style={{ width: 320, borderLeft: '1px solid #e8e8e8', background: '#fafafa', position: 'relative', flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '10px 12px 0', flexShrink: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <button
            onClick={onToggleCollapse}
            title="折叠属性面板"
            style={{
              width: 20, height: 20, borderRadius: 3,
              border: 'none', background: 'transparent',
              cursor: 'pointer', fontSize: 12, color: '#999',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            ▶
          </button>
          <span style={{ fontWeight: 600, fontSize: 14 }}>属性面板</span>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
          <div style={{ color: '#999' }}>选择节点查看属性</div>
        </div>
      </div>
    );
  }

  if (!entry) {
    return (
      <div style={{ width: 320, borderLeft: '1px solid #e8e8e8', background: '#fafafa', position: 'relative', flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '10px 12px 0', flexShrink: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <button
            onClick={onToggleCollapse}
            title="折叠属性面板"
            style={{
              width: 20, height: 20, borderRadius: 3,
              border: 'none', background: 'transparent',
              cursor: 'pointer', fontSize: 12, color: '#999',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            ▶
          </button>
          <span style={{ fontWeight: 600, fontSize: 14 }}>属性面板</span>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
          <div style={{ color: '#999' }}>未知节点类型: {nodeType}</div>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        width: 320,
        borderLeft: '1px solid #e8e8e8',
        background: '#fff',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        position: 'relative',
        flexShrink: 0,
      }}
    >
      {/* Fixed header — always visible */}
      <div style={{ padding: '10px 12px 0', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 8 }}>
          <button
            onClick={onToggleCollapse}
            title="折叠属性面板"
            style={{
              width: 20, height: 20, borderRadius: 3,
              border: 'none', background: 'transparent',
              cursor: 'pointer', fontSize: 12, color: '#999',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            ▶
          </button>
          {(nodeData._seq != null) && <SeqBadge seq={nodeData._seq as number} size="lg" />}
          {entry.icon}
          <span style={{ fontWeight: 600, fontSize: 14 }}>{entry.label} 节点</span>
          {entry.category && (
            <Tag color="blue" style={{ fontSize: 10, marginLeft: 4 }}>{entry.category}</Tag>
          )}
        </div>
      </div>

      {/* Scrollable body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 12px 12px' }}>

      {/* === Section 1: Port Info === */}
      {ports.length > 0 && (
        <Section title="端口信息">
          {inputPorts.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <div style={{ fontSize: 10, color: '#888', marginBottom: 4 }}>入口 (Input)</div>
              {inputPorts.map((port) => {
                const connectedEdge = incomingEdges.find((e) => e.targetHandle === port.key);
                const connectedMatch = connectedEdge?.data?.matchStatus;
                return (
                  <div key={port.key} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3, fontSize: 11 }}>
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: PORT_COLORS[port.type] || '#d9d9d9',
                        display: 'inline-block',
                        flexShrink: 0,
                      }}
                    />
                    <span style={{ color: '#333' }}>{port.label}</span>
                    <Tag style={{ fontSize: 9, margin: 0 }} color={PORT_COLORS[port.type]}>{port.type}</Tag>
                    {connectedEdge && (
                      <Tag
                        style={{ fontSize: 9, margin: 0 }}
                        color={connectedMatch === 'matched' ? 'green' : connectedMatch === 'mismatched' ? 'red' : 'default'}
                      >
                        {connectedMatch === 'matched' ? '已匹配' : connectedMatch === 'mismatched' ? '不匹配' : '未知'}
                      </Tag>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          {outputPorts.length > 0 && (
            <div>
              <div style={{ fontSize: 10, color: '#888', marginBottom: 4 }}>出口 (Output)</div>
              {outputPorts.map((port) => {
                const connectedEdge = outgoingEdges.find((e) => e.sourceHandle === port.key);
                const connectedMatch = connectedEdge?.data?.matchStatus;
                return (
                  <div key={port.key} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3, fontSize: 11 }}>
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: PORT_COLORS[port.type] || '#d9d9d9',
                        display: 'inline-block',
                        flexShrink: 0,
                      }}
                    />
                    <span style={{ color: '#333' }}>{port.label}</span>
                    <Tag style={{ fontSize: 9, margin: 0 }} color={PORT_COLORS[port.type]}>{port.type}</Tag>
                    {connectedEdge && (
                      <Tag
                        style={{ fontSize: 9, margin: 0 }}
                        color={connectedMatch === 'matched' ? 'green' : connectedMatch === 'mismatched' ? 'red' : 'default'}
                      >
                        {connectedMatch === 'matched' ? '已匹配' : connectedMatch === 'mismatched' ? '不匹配' : '未知'}
                      </Tag>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </Section>
      )}

      {/* === Section 2: Parameters === */}
      <Section title="参数">
        {nodeType === 'p4file' && (
          <FieldInput label="P4 文件路径" value={(nodeData.p4Path as string) || ''} onChange={(v) => handleFieldChange('p4Path', v)} placeholder="//C7/.../file.xlsx" required />
        )}
        {nodeType === 'excel' && (
          <>
            <FieldSelect
              label="Sheet 名"
              value={(nodeData.sheetName as string) || ''}
              onChange={(v) => handleFieldChange('sheetName', v)}
              options={runOutput?.sheetNames ? (runOutput.sheetNames as string[]).map((s: string) => ({ label: s, value: s })) : []}
              placeholder={runOutput?.sheetNames ? '选择工作表' : '运行后加载选项'}
            />
            <FieldMultiSelect
              label="筛选行"
              value={(nodeData.filterRows as string[]) || []}
              onChange={(v) => handleFieldChange('filterRows', v)}
              options={(() => {
                const rows = (runOutput?.allRows ?? runOutput?.rows) as Record<string, any>[] | undefined;
                const cols = (runOutput?.allColumns ?? runOutput?.columns) as string[] | undefined;
                if (!rows || !cols || cols.length === 0) return [];
                const firstCol = cols[0];
                return rows.map((row: Record<string, any>, i: number) => {
                  const label = String(row[firstCol] ?? `第 ${i + 1} 行`);
                  return { label, value: label };
                });
              })()}
            />
            <FieldMultiSelect
              label="筛选列"
              value={(nodeData.filterColumns as string[]) || []}
              onChange={(v) => handleFieldChange('filterColumns', v)}
              options={runOutput?.allColumns
                ? (runOutput.allColumns as string[]).map((c: string) => ({ label: c, value: c }))
                : runOutput?.columns
                  ? runOutput.columns.map((c: string) => ({ label: c, value: c }))
                  : []}
            />
          </>
        )}
        {nodeType === 'lua' && (
          <FieldInput label="入口函数（可选）" value={(nodeData.entryFunction as string) || ''} onChange={(v) => handleFieldChange('entryFunction', v)} placeholder="入口函数名" />
        )}
        {nodeType === 'json' && (
          (() => {
            const jsonPathLocked = incomingEdges.some((e) => e.targetHandle === 'jsonPath');
            return (
              <div style={{ marginBottom: 12 }}>
                <label style={{ display: 'block', marginBottom: 4, fontSize: 11, color: '#666' }}>
                  JSON Path（可选）
                  {jsonPathLocked && (
                    <span style={{
                      marginLeft: 8, fontSize: 10, fontWeight: 400,
                      color: '#2f54eb', background: '#f0f5ff', border: '1px solid #adc6ff',
                      borderRadius: 3, padding: '1px 6px',
                    }}>
                      🔗 由连线提供
                    </span>
                  )}
                </label>
                <input
                  type="text"
                  value={(nodeData.jsonPath as string) || ''}
                  disabled={jsonPathLocked}
                  onChange={(e) => !jsonPathLocked && handleFieldChange('jsonPath', e.target.value)}
                  placeholder={jsonPathLocked ? '由连线提供' : '如 $.data.items'}
                  style={{
                    width: '100%',
                    padding: '4px 8px',
                    border: '1px solid #d9d9d9',
                    borderRadius: 4,
                    fontSize: 12,
                    boxSizing: 'border-box',
                    background: jsonPathLocked ? '#f5f5f5' : '#fff',
                    color: jsonPathLocked ? '#aaa' : '#333',
                    cursor: jsonPathLocked ? 'not-allowed' : 'text',
                  }}
                />
              </div>
            );
          })()
        )}
        {nodeType === 'prompt' && (
          <>
            <FieldTextarea label="提示词" value={(nodeData.prompt as string) || ''} onChange={(v) => handleFieldChange('prompt', v)} placeholder="输入提示词" rows={4} required />
            <FieldInput label="模型" value={(nodeData.model as string) || 'qwen-plus'} onChange={(v) => handleFieldChange('model', v)} placeholder="模型名称" />
            <FieldInput label="温度" value={String((nodeData.temperature as number) || 0.7)} onChange={(v) => handleFieldChange('temperature', parseFloat(v) || 0)} placeholder="0.0 - 1.0" type="number" />
          </>
        )}
      </Section>

      {/* === Section 3: Input Content === */}
      <Section title="输入内容" defaultOpen={inputPorts.length > 0}>
        {inputPorts.length === 0 ? (
          <div style={{ fontSize: 11, color: '#999' }}>此节点无输入端口</div>
        ) : upstreamData.length > 0 ? (
          <div style={{ fontSize: 11, color: '#333' }}>
            {upstreamData.map((u) => (
              <div key={u.tgtHandle} style={{ marginBottom: 8, padding: '4px 6px', background: '#f5f5f5', borderRadius: 3 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
                  <span
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: '50%',
                      background: PORT_COLORS[u.tgtPortType] || '#d9d9d9',
                      display: 'inline-block',
                    }}
                  />
                  <span style={{ fontWeight: 600 }}>{u.tgtPortLabel}</span>
                  {u.hasData ? (
                    <Tag style={{ fontSize: 9, margin: 0 }} color="green">已接收</Tag>
                  ) : (
                    <Tag style={{ fontSize: 9, margin: 0 }} color="orange">未接收</Tag>
                  )}
                  {u.hasData && u.preview && !u.isBinary && (
                    <Button
                      size="small"
                      icon={<ExpandOutlined />}
                      style={{ fontSize: 10, padding: '0 6px', height: 20 }}
                      onClick={() => { setModalContent(u.preview || ''); setModalTitle(`输入内容 - ${u.tgtPortLabel}`); setInputModalOpen(true); }}
                    >
                      弹窗查看
                    </Button>
                  )}
                </div>
                <div style={{ fontSize: 10, color: '#999', marginBottom: 4 }}>
                  来自 {u.sourceId} → {u.srcHandle || '全部输出'}
                </div>
                {u.hasData && u.preview && !u.isBinary && (
                  <pre
                    style={{
                      margin: 0,
                      padding: '4px 6px',
                      background: '#fff',
                      border: '1px solid #e8e8e8',
                      borderRadius: 3,
                      maxHeight: 80,
                      overflowY: 'auto',
                      fontSize: 9,
                      color: '#333',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                    }}
                  >
                    {u.preview}
                  </pre>
                )}
                {u.hasData && u.isBinary && (
                  <div style={{ fontSize: 10, color: '#999', padding: '2px 6px', background: '#f9f9f9', borderRadius: 3 }}>
                    📦 二进制文件内容（不可预览）
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 11, color: '#999' }}>未连接上游节点</div>
        )}
      </Section>

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <Button type="primary" loading={running} onClick={handleRunNode} style={{ flex: 1 }}>
          运行节点
        </Button>
      </div>

      {/* === Section 4: Run Info === */}
      <Section title="运行信息" defaultOpen={runStatus !== 'idle'}>
        {runStatus === 'idle' ? (
          <div style={{ fontSize: 11, color: '#999' }}>尚未运行</div>
        ) : (
          <div style={{ fontSize: 11 }}>
            <div style={{ marginBottom: 4 }}>
              <span style={{ color: '#666' }}>状态：</span>
              <Tag
                color={runStatus === 'success' ? 'green' : runStatus === 'error' ? 'red' : runStatus === 'running' ? 'blue' : 'default'}
                style={{ fontSize: 10 }}
              >
                {runStatus === 'running' ? '运行中...' : runStatus === 'success' ? '成功' : runStatus === 'error' ? '失败' : '空闲'}
              </Tag>
            </div>
            {runStatus === 'error' && runOutput?.error && (
              <div style={{ color: '#cf1322', background: '#fff2f0', padding: '4px 6px', borderRadius: 3, marginTop: 4 }}>
                {runOutput.error}
              </div>
            )}
          </div>
        )}
      </Section>

      {/* === Section 5: Output Content — structured per output port === */}
      <Section title="输出内容" defaultOpen={runStatus === 'success' || runStatus === 'error'}>
        {runStatus === 'idle' || runStatus === 'running' ? (
          <div style={{ fontSize: 11, color: '#999' }}>
            {runStatus === 'running' ? '运行中...' : '运行后显示结果'}
          </div>
        ) : runStatus === 'error' ? (
          <div style={{ marginBottom: 8, padding: '4px 6px', background: '#fff2f0', borderRadius: 3, border: '1px solid #ffccc7' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#ff4d4f', display: 'inline-block' }} />
              <span style={{ fontWeight: 600, fontSize: 11, color: '#cf1322' }}>错误</span>
            </div>
            <pre style={{ margin: 0, padding: '4px 6px', background: '#fff', border: '1px solid #ffccc7', borderRadius: 3, fontSize: 9, whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: '#cf1322' }}>
              {typeof runOutput === 'string' ? runOutput : runOutput?.error || JSON.stringify(stripRuntimeMeta(runOutput), null, 2)}
            </pre>
          </div>
        ) : outputPorts.length > 0 ? (
          outputPorts.map((p) => {
            const portValue = runOutput?.[p.key];
            const hasValue = portValue !== undefined && portValue !== null;
            const displayValue = hasValue ? portValue : (outputPorts.length === 1 ? stripRuntimeMeta(runOutput) : undefined);
            const hasDisplay = displayValue !== undefined && displayValue !== null;
            // For Diff node: show side-by-side diff instead of raw output
            const isDiffPort = nodeType === 'diff' && p.key === 'isSame' && runOutput?.contentA !== undefined && runOutput?.contentB !== undefined;
            // For Table node: 'tables' port is an array of {title, columns, rows}
            const isTablesPort = p.key === 'tables' && Array.isArray(displayValue) && displayValue.length > 0 && displayValue[0]?.columns;
            // For Excel node: table-data port with columns+rows structure
            const isExcelPort = !isTablesPort && p.type === 'table-data' && displayValue?.columns;
            // For Excel node: only merge allSheets when no specific sheetName is selected
            const hasSheetNameSelected = !!(nodeData.sheetName as string);
            const excelDataPort = isExcelPort && nodeType === 'excel' && runOutput?.allSheets
              ? { ...displayValue, activeSheetName: hasSheetNameSelected ? (nodeData.sheetName as string) : undefined, allSheets: hasSheetNameSelected ? undefined : runOutput.allSheets, sheetNames: runOutput.sheetNames }
              : isExcelPort ? { ...displayValue, activeSheetName: (nodeData.sheetName as string) || undefined }
              : displayValue;
            const previewText = hasDisplay && !isDiffPort && !isTablesPort && !isExcelPort
              ? (typeof displayValue === 'string' 
                  ? (isBinaryContent(displayValue) ? '📦 二进制文件，不支持文本预览' : displayValue) 
                  : (() => {
                      const json = stripRuntimeMeta(displayValue);
                      if (typeof json === 'object' && json?.fileContent && typeof json.fileContent === 'string' && isBinaryContent(json.fileContent)) {
                        const { fileContent, ...rest } = json;
                        return JSON.stringify({ ...rest, fileContent: '📦 二进制文件' }, null, 2);
                      }
                      return JSON.stringify(json, null, 2);
                    })())
              : null;

            return (
              <div key={p.key} style={{ marginBottom: 8, padding: '4px 6px', background: '#f5f5f5', borderRadius: 3, border: '1px solid #e8e8e8' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
                  <span
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: '50%',
                      background: PORT_COLORS[p.type] || '#d9d9d9',
                      display: 'inline-block',
                    }}
                  />
                  <span style={{ fontWeight: 600 }}>{p.label}</span>
                  {hasDisplay ? (
                    <Tag style={{ fontSize: 9, margin: 0 }} color="green">有输出</Tag>
                  ) : (
                    <Tag style={{ fontSize: 9, margin: 0 }} color="orange">无输出</Tag>
                  )}
                  <Tag style={{ fontSize: 9, margin: 0 }}>{p.type}</Tag>
                  {hasDisplay && previewText && (
                    <Button
                      size="small"
                      icon={<ExpandOutlined />}
                      style={{ fontSize: 10, padding: '0 6px', height: 20 }}
                      onClick={() => { setModalContent(previewText || ''); setModalTitle(`输出内容 - ${p.label}`); setOutputModalOpen(true); }}
                    >
                      弹窗查看
                    </Button>
                  )}
                </div>
                {/* Content area: Tables for table node, Univer for Excel, DiffSummary for diff node, pre for others */}
                {hasDisplay && isTablesPort ? (
                  <div style={{ background: '#fff', border: '1px solid #e8e8e8', borderRadius: 3, overflow: 'hidden' }}>
                    {(displayValue as TableData[]).map((t: TableData, i: number) => (
                      <MiniTable key={i} table={t} maxRows={20} compact />
                    ))}
                  </div>
                ) : hasDisplay && isExcelPort ? (
                  <Suspense fallback={<pre style={{ margin: 0, padding: '4px 6px', fontSize: 9 }}>{JSON.stringify(excelDataPort, null, 2).slice(0, 200)}...</pre>}>
                    <UniverRenderer data={excelDataPort} nodeId={selectedNode?.id} compact height={300} />
                  </Suspense>
                ) : hasDisplay && isDiffPort ? (
                  <DiffSummary
                    contentA={String(runOutput.contentA ?? '')}
                    contentB={String(runOutput.contentB ?? '')}
                    isSame={!!runOutput.isSame}
                    stats={runOutput.stats}
                    unifiedDiff={runOutput.unifiedDiff ?? ''}
                    maxLines={15}
                    height={160}
                  />
                ) : hasDisplay && previewText ? (
                  /^https?:\/\//i.test(previewText) ? (
                    <a href={previewText} target="_blank" rel="noopener noreferrer"
                       style={{ color: '#1890ff', textDecoration: 'underline', fontSize: 10, wordBreak: 'break-all' }}>
                      {p.key === 'taskUrl' || p.label === '任务链接' ? '🔗 查看任务' : previewText}
                    </a>
                  ) : (
                  <pre
                    style={{
                      margin: 0,
                      padding: '4px 6px',
                      background: '#fff',
                      border: '1px solid #e8e8e8',
                      borderRadius: 3,
                      maxHeight: 120,
                      overflowY: 'auto',
                      fontSize: 9,
                      color: '#333',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                    }}
                  >
                    {previewText}
                  </pre>
                  )
                ) : null}
              </div>
            );
          })
        ) : (
          <>
            <div style={{ marginBottom: 8 }}>
              <Button
                size="small"
                icon={<ExpandOutlined />}
                onClick={() => { setModalContent(outputText); setModalTitle('输出内容'); setOutputModalOpen(true); }}
                disabled={!outputText}
              >
                弹窗查看
              </Button>
            </div>
            <pre
              style={{
                margin: 0,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
                maxHeight: 200,
                overflowY: 'auto',
                fontSize: 10,
                color: '#333',
                background: '#f9f9f9',
                padding: '6px 8px',
                borderRadius: 3,
                border: '1px solid #e8e8e8',
              }}
            >
              {outputText}
            </pre>
          </>
        )}
      </Section>

      {/* Shared Modal for long content (input or output) */}
      <Modal
        title={modalTitle}
        open={inputModalOpen || outputModalOpen}
        onCancel={() => { setInputModalOpen(false); setOutputModalOpen(false); }}
        width={800}
        footer={[
          <Button key="copy" icon={<CopyOutlined />} onClick={() => copyToClipboard(modalContent)}>
            复制
          </Button>,
          <Button key="close" type="primary" onClick={() => { setInputModalOpen(false); setOutputModalOpen(false); }}>
            关闭
          </Button>,
        ]}
      >
        <pre
          style={{
            margin: 0,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
            maxHeight: '70vh',
            overflowY: 'auto',
            fontSize: 11,
            color: '#333',
            background: '#f9f9f9',
            padding: 12,
            borderRadius: 4,
            border: '1px solid #e8e8e8',
          }}
        >
          {modalContent}
        </pre>
      </Modal>
      </div>{/* end scrollable body */}
    </div>
  );
};

/** Reusable field components */
function FieldInput({ label, value, onChange, placeholder, type = 'text', required = false }: {
  label: string; value: string; onChange: (v: string) => void; placeholder: string; type?: string; required?: boolean;
}) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={{ display: 'block', marginBottom: 4, fontSize: 11, color: '#666' }}>
        {label}{required && <span style={{ color: '#ff4d4f', marginLeft: 2 }}>*</span>}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          width: '100%',
          padding: '4px 8px',
          border: `1px solid ${required && !value ? '#ffccc7' : '#d9d9d9'}`,
          borderRadius: 4,
          fontSize: 12,
          boxSizing: 'border-box',
        }}
      />
    </div>
  );
}

function FieldTextarea({ label, value, onChange, placeholder, rows = 3, required = false }: {
  label: string; value: string; onChange: (v: string) => void; placeholder: string; rows?: number; required?: boolean;
}) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={{ display: 'block', marginBottom: 4, fontSize: 11, color: '#666' }}>
        {label}{required && <span style={{ color: '#ff4d4f', marginLeft: 2 }}>*</span>}
      </label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        style={{
          width: '100%',
          padding: '4px 8px',
          border: `1px solid ${required && !value ? '#ffccc7' : '#d9d9d9'}`,
          borderRadius: 4,
          resize: 'vertical',
          fontSize: 12,
          boxSizing: 'border-box',
        }}
      />
    </div>
  );
}

function FieldSelect({ label, value, onChange, options, placeholder }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { label: string; value: string }[];
  placeholder?: string;
}) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={{ display: 'block', marginBottom: 4, fontSize: 11, color: '#666' }}>
        {label}
      </label>
      <Select
        size="small"
        value={value || undefined}
        onChange={onChange}
        options={options}
        placeholder={placeholder || (options.length === 0 ? '运行节点后加载选项' : '选择...')}
        style={{ width: '100%', fontSize: 11 }}
        allowClear
        showSearch
        optionFilterProp="label"
        getPopupContainer={(node) => node.parentElement || document.body}
        styles={{ popup: { root: { fontSize: 11 } } }}
      />
    </div>
  );
}

function FieldMultiSelect({ label, value, onChange, options }: {
  label: string;
  value: string[];
  onChange: (v: string[]) => void;
  options: { label: string; value: string }[];
}) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={{ display: 'block', marginBottom: 4, fontSize: 11, color: '#666' }}>
        {label}
        {value.length > 0 && <span style={{ color: '#1890ff', marginLeft: 6 }}>({value.length} 项)</span>}
      </label>
      <Select
        mode="multiple"
        size="small"
        value={value}
        onChange={onChange}
        options={options}
        placeholder={options.length === 0 ? '运行节点后加载选项' : '选择...'}
        style={{ width: '100%', fontSize: 11 }}
        allowClear
        showSearch
        optionFilterProp="label"
        maxTagCount={3}
        maxTagTextLength={10}
        getPopupContainer={(node) => node.parentElement || document.body}
        styles={{ popup: { root: { fontSize: 11 } } }}
      />
    </div>
  );
}

export default PropertyPanel;
