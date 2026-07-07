import React, { useCallback, useState } from 'react';
import type { Node, Edge } from 'reactflow';
import { getNodeRegistry } from './NodeRegistry';
import { Button, Tag, Modal, message } from 'antd';
import { ExpandOutlined, CopyOutlined } from '@ant-design/icons';
import { FlowApi } from './services/FlowApi';
import type { RunStatus } from './nodes/BaseNode';
import { getNodePorts, type PortDefinition } from './PortTypes';

const PORT_COLORS: Record<string, string> = {
  'file-content': '#1890ff',
  'file-path': '#722ed1',
  'any': '#8c8c8c',
  'text': '#fa8c16',
  'table-data': '#52c41a',
  'json-data': '#13c2c2',
};

/** Section wrapper */
function Section({ title, children, defaultOpen = true }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ marginBottom: 12, border: '1px solid #e8e8e8', borderRadius: 6, overflow: 'hidden' }}>
      <div
        onClick={() => setOpen(!open)}
        style={{
          padding: '6px 10px',
          background: '#fafafa',
          fontWeight: 600,
          fontSize: 12,
          color: '#333',
          cursor: 'pointer',
          display: 'flex',
          justifyContent: 'space-between',
          userSelect: 'none',
        }}
      >
        <span>{title}</span>
        <span style={{ fontSize: 10, color: '#999' }}>{open ? '▼' : '▶'}</span>
      </div>
      {open && <div style={{ padding: '8px 10px' }}>{children}</div>}
    </div>
  );
}

interface PropertyPanelProps {
  selectedNode: Node | null;
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  edges: Edge[];
  nodes: Node[];
}

const PropertyPanel: React.FC<PropertyPanelProps> = ({ selectedNode, setNodes, edges, nodes }) => {
  // ALL hooks must be called before any conditional return
  const [outputModalOpen, setOutputModalOpen] = useState(false);
  const [inputModalOpen, setInputModalOpen] = useState(false);
  const [modalContent, setModalContent] = useState('');
  const [modalTitle, setModalTitle] = useState('');

  const nodeType = selectedNode?.type ?? '';
  const nodeData = (selectedNode?.data || {}) as Record<string, unknown>;
  const entry = selectedNode ? getNodeRegistry(nodeType) : null;

  const runStatus = (nodeData._runStatus as RunStatus) || 'idle';
  const runOutput = nodeData._runOutput as any;
  const running = runStatus === 'running';

  const ports = getNodePorts(nodeType);
  const inputPorts = ports.filter((p) => p.direction === 'input');
  const outputPorts = ports.filter((p) => p.direction === 'output');

  const incomingEdges = selectedNode ? edges.filter((e) => e.target === selectedNode.id) : [];
  const outgoingEdges = selectedNode ? edges.filter((e) => e.source === selectedNode.id) : [];

  // Collect upstream data per input port — includes actual output preview
  const upstreamData = incomingEdges
    .filter((e) => e.data?.matchStatus === 'matched')
    .map((e) => {
      const srcHandle = e.sourceHandle;
      const tgtHandle = e.targetHandle;
      const tgtPort = inputPorts.find((p) => p.key === tgtHandle);
      // Read upstream node's actual output
      const srcNode = nodes.find((n) => n.id === e.source);
      const srcOutput = (srcNode?.data as any)?._runOutput;
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
        preview: previewValue !== undefined
          ? (typeof previewValue === 'string' ? previewValue : JSON.stringify(previewValue, null, 2))
          : null,
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
    const upstreamInput: Record<string, any> = {};

    setNodes((nds) => {
      for (const edge of incomingEdges) {
        const srcNode = nds.find((n) => n.id === edge.source);
        if (!srcNode) continue;
        const srcOutput = (srcNode.data as any)?._runOutput;
        if (!srcOutput || srcOutput.error) continue;
        if (edge.sourceHandle && srcOutput[edge.sourceHandle] !== undefined) {
          upstreamInput[edge.targetHandle || edge.sourceHandle] = srcOutput[edge.sourceHandle];
        } else {
          Object.assign(upstreamInput, srcOutput);
        }
      }
      return nds.map((n) =>
        n.id === selectedNode.id
          ? { ...n, data: { ...n.data, _runStatus: 'running', _runOutput: null } }
          : n,
      );
    });

    try {
      // Build clean config — strip internal state keys (_runStatus, _runOutput, etc.)
      const cleanConfig: Record<string, any> = {};
      for (const [k, v] of Object.entries(nodeData)) {
        if (!k.startsWith('_') && v !== undefined && v !== null && String(v).trim() !== '') {
          cleanConfig[k] = v;
        }
      }
      const result = await FlowApi.runNode(nodeType, cleanConfig, upstreamInput);
      const output = result.output ?? result;
      const newStatus = output?.error ? 'error' : 'success';
      setNodes((nds) =>
        nds.map((n) =>
          n.id === selectedNode.id
            ? { ...n, data: { ...n.data, _runStatus: newStatus, _runOutput: output } }
            : n,
        ),
      );
      if (output?.error) {
        message.error(`运行失败: ${output.error}`);
      } else {
        message.success('节点运行完成');
      }
    } catch (err: any) {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === selectedNode.id
            ? { ...n, data: { ...n.data, _runStatus: 'error', _runOutput: { error: err.message } } }
            : n,
        ),
      );
      message.error(`运行失败: ${err.message}`);
    }
  }, [selectedNode, nodeType, nodeData, setNodes, incomingEdges]);

  // Format output for display
  const formatOutput = (output: any): string => {
    if (typeof output === 'string') return output;
    if (output?.fileContent && typeof output.fileContent === 'string') return output.fileContent;
    if (output?.error) return output.error;
    return JSON.stringify(output, null, 2);
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
  if (!selectedNode) {
    return (
      <div style={{ width: 320, borderLeft: '1px solid #e8e8e8', padding: 16, background: '#fafafa' }}>
        <div style={{ color: '#999' }}>选择节点查看属性</div>
      </div>
    );
  }

  if (!entry) {
    return (
      <div style={{ width: 320, borderLeft: '1px solid #e8e8e8', padding: 16, background: '#fafafa' }}>
        <div style={{ color: '#999' }}>未知节点类型: {nodeType}</div>
      </div>
    );
  }

  return (
    <div
      style={{
        width: 320,
        borderLeft: '1px solid #e8e8e8',
        padding: 12,
        background: '#fff',
        overflowY: 'auto',
        height: '100%',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        {entry.icon}
        <span style={{ fontWeight: 600, fontSize: 14 }}>{entry.label} 节点</span>
        {entry.category && (
          <Tag color="blue" style={{ fontSize: 10, marginLeft: 4 }}>{entry.category}</Tag>
        )}
      </div>

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
            <FieldInput label="工作表名（可选）" value={(nodeData.sheet as string) || ''} onChange={(v) => handleFieldChange('sheet', v)} placeholder="工作表名" />
            <FieldMultiSelect
              label="行筛选"
              value={(nodeData.rowFilter as string[]) || []}
              onChange={(v) => handleFieldChange('rowFilter', v)}
              options={runOutput?.columns ? Array.from({ length: runOutput.rows?.length || 0 }, (_, i) => ({ label: `第 ${i + 1} 行`, value: String(i + 1) })) : []}
            />
            <FieldMultiSelect
              label="列筛选"
              value={(nodeData.columnFilter as string[]) || []}
              onChange={(v) => handleFieldChange('columnFilter', v)}
              options={runOutput?.columns ? runOutput.columns.map((c: string) => ({ label: c, value: c })) : []}
            />
          </>
        )}
        {nodeType === 'lua' && (
          <FieldInput label="入口函数（可选）" value={(nodeData.entryFunction as string) || ''} onChange={(v) => handleFieldChange('entryFunction', v)} placeholder="入口函数名" />
        )}
        {nodeType === 'json' && (
          <FieldInput label="JSON Path（可选）" value={(nodeData.jsonPath as string) || ''} onChange={(v) => handleFieldChange('jsonPath', v)} placeholder="如 $.data.items" />
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
                  {u.hasData && u.preview && (
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
                {u.hasData && u.preview && (
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
              </div>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 11, color: '#999' }}>未连接上游节点</div>
        )}
      </Section>

      {/* Run button */}
      <Button type="primary" loading={running} onClick={handleRunNode} block style={{ marginBottom: 12 }}>
        运行节点
      </Button>

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

      {/* === Section 5: Output Content === */}
      <Section title="输出内容" defaultOpen={runStatus === 'success' || runStatus === 'error'}>
        {runStatus === 'idle' || runStatus === 'running' ? (
          <div style={{ fontSize: 11, color: '#999' }}>
            {runStatus === 'running' ? '运行中...' : '运行后显示结果'}
          </div>
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
                background: runStatus === 'error' ? '#fff2f0' : '#f9f9f9',
                padding: '6px 8px',
                borderRadius: 3,
                border: `1px solid ${runStatus === 'error' ? '#ffccc7' : '#e8e8e8'}`,
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
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxHeight: 120, overflowY: 'auto' }}>
        {options.length === 0 && (
          <span style={{ fontSize: 10, color: '#999' }}>运行节点后加载选项</span>
        )}
        {options.map((opt) => {
          const isSelected = value.includes(opt.value);
          return (
            <span
              key={opt.value}
              onClick={() => {
                const next = isSelected
                  ? value.filter((v) => v !== opt.value)
                  : [...value, opt.value];
                onChange(next);
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

export default PropertyPanel;
