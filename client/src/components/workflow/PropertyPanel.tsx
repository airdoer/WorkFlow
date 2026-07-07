import React, { useCallback } from 'react';
import type { Node, Edge } from 'reactflow';
import { getNodeRegistry } from './NodeRegistry';
import { Button, message, Tag } from 'antd';
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

interface PropertyPanelProps {
  selectedNode: Node | null;
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  edges: Edge[];
}

const PropertyPanel: React.FC<PropertyPanelProps> = ({ selectedNode, setNodes, edges }) => {
  if (!selectedNode) {
    return (
      <div style={{ width: 300, borderLeft: '1px solid #e8e8e8', padding: 16, background: '#fafafa' }}>
        <div style={{ color: '#999' }}>选择节点查看属性</div>
      </div>
    );
  }

  const nodeType = selectedNode.type ?? '';
  const nodeData = (selectedNode.data || {}) as Record<string, unknown>;
  const entry = getNodeRegistry(nodeType);

  if (!entry) {
    return (
      <div style={{ width: 300, borderLeft: '1px solid #e8e8e8', padding: 16, background: '#fafafa' }}>
        <div style={{ color: '#999' }}>未知节点类型: {nodeType}</div>
      </div>
    );
  }

  const runStatus = (nodeData._runStatus as RunStatus) || 'idle';
  const runOutput = nodeData._runOutput as any;
  const running = runStatus === 'running';

  // Get ports info
  const ports = getNodePorts(nodeType);
  const inputPorts = ports.filter((p) => p.direction === 'input');
  const outputPorts = ports.filter((p) => p.direction === 'output');

  // Get connected edges for this node
  const incomingEdges = edges.filter((e) => e.target === selectedNode.id);
  const outgoingEdges = edges.filter((e) => e.source === selectedNode.id);

  const handleFieldChange = (fieldName: string, value: any) => {
    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedNode.id
          ? { ...n, data: { ...n.data, [fieldName]: value } }
          : n,
      ),
    );
  };

  const handleRunNode = useCallback(async () => {
    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedNode.id
          ? { ...n, data: { ...n.data, _runStatus: 'running', _runOutput: null } }
          : n,
      ),
    );

    try {
      const result = await FlowApi.runNode(nodeType, nodeData, {});
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
  }, [selectedNode.id, nodeType, nodeData, setNodes]);

  return (
    <div
      style={{
        width: 300,
        borderLeft: '1px solid #e8e8e8',
        padding: 16,
        background: '#fff',
        overflowY: 'auto',
        height: '100%',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        {entry.icon}
        <span style={{ fontWeight: 600, fontSize: 15 }}>{entry.label} 节点</span>
        {entry.category && (
          <Tag color="blue" style={{ fontSize: 10, marginLeft: 4 }}>{entry.category}</Tag>
        )}
      </div>

      {/* Port info section */}
      {ports.length > 0 && (
        <div style={{ marginBottom: 16, padding: 10, background: '#f9f9f9', borderRadius: 6, border: '1px solid #e8e8e8' }}>
          <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 8, color: '#333' }}>端口信息</div>

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
        </div>
      )}

      {/* Node type specific fields */}
      <div style={{ marginBottom: 16 }}>
        {nodeType === 'p4file' && (
          <>
            <FieldInput label="P4 文件路径" value={(nodeData.p4Path as string) || ''} onChange={(v) => handleFieldChange('p4Path', v)} placeholder="//C7/.../file.xlsx" />
          </>
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
          <>
            <FieldInput label="入口函数（可选）" value={(nodeData.entryFunction as string) || ''} onChange={(v) => handleFieldChange('entryFunction', v)} placeholder="入口函数名" />
          </>
        )}
        {nodeType === 'json' && (
          <>
            <FieldInput label="JSON Path（可选）" value={(nodeData.jsonPath as string) || ''} onChange={(v) => handleFieldChange('jsonPath', v)} placeholder="如 $.data.items" />
          </>
        )}
        {nodeType === 'prompt' && (
          <>
            <FieldTextarea label="提示词" value={(nodeData.prompt as string) || ''} onChange={(v) => handleFieldChange('prompt', v)} placeholder="输入提示词，支持 {{nodeId.outputKey}} 变量" rows={6} />
            <FieldInput label="模型" value={(nodeData.model as string) || 'qwen-plus'} onChange={(v) => handleFieldChange('model', v)} placeholder="模型名称" />
            <FieldInput label="温度" value={String((nodeData.temperature as number) || 0.7)} onChange={(v) => handleFieldChange('temperature', parseFloat(v) || 0)} placeholder="0.0 - 1.0" type="number" />
          </>
        )}
      </div>

      <Button type="primary" loading={running} onClick={handleRunNode} block>
        运行节点
      </Button>

      {/* Run result */}
      {runStatus !== 'idle' && runStatus !== 'running' && runOutput && (
        <div
          style={{
            marginTop: 12,
            background: runStatus === 'error' ? '#fff2f0' : '#f6ffed',
            border: `1px solid ${runStatus === 'error' ? '#ffccc7' : '#b7eb8f'}`,
            borderRadius: 4,
            fontSize: 12,
          }}
        >
          <div style={{ padding: '6px 8px', fontWeight: 600, color: runStatus === 'error' ? '#cf1322' : '#389e0d' }}>
            {runStatus === 'error' ? '❌ 运行错误' : '✅ 运行结果'}
          </div>
          <pre
            style={{
              margin: 0,
              padding: '6px 8px',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
              maxHeight: 400,
              overflowY: 'auto',
              fontSize: 11,
              color: '#333',
              borderTop: `1px solid ${runStatus === 'error' ? '#ffccc7' : '#b7eb8f'}`,
            }}
          >
            {typeof runOutput === 'string'
              ? runOutput
              : JSON.stringify(runOutput, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};

/** Reusable field components */
function FieldInput({ label, value, onChange, placeholder, type = 'text' }: {
  label: string; value: string; onChange: (v: string) => void; placeholder: string; type?: string;
}) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: '#666' }}>{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        style={{ width: '100%', padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 4, fontSize: 12, boxSizing: 'border-box' }}
      />
    </div>
  );
}

function FieldTextarea({ label, value, onChange, placeholder, rows = 3 }: {
  label: string; value: string; onChange: (v: string) => void; placeholder: string; rows?: number;
}) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: '#666' }}>{label}</label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        style={{ width: '100%', padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 4, resize: 'vertical', fontSize: 12, boxSizing: 'border-box' }}
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
      <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: '#666' }}>
        {label}
        {value.length > 0 && <span style={{ color: '#1890ff', marginLeft: 6 }}>({value.length} 项)</span>}
      </label>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxHeight: 150, overflowY: 'auto' }}>
        {options.length === 0 && (
          <span style={{ fontSize: 11, color: '#999' }}>运行节点后加载选项</span>
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
