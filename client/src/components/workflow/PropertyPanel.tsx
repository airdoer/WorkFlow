import React, { useCallback } from 'react';
import type { Node } from 'reactflow';
import { getNodeRegistry } from './NodeRegistry';
import { Button, message } from 'antd';
import { FlowApi } from './services/FlowApi';
import type { RunStatus } from './nodes/BaseNode';

interface PropertyPanelProps {
  selectedNode: Node | null;
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
}

const PropertyPanel: React.FC<PropertyPanelProps> = ({ selectedNode, setNodes }) => {
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

  // Read run status/output from node data — each node has its own isolated data
  const runStatus = (nodeData._runStatus as RunStatus) || 'idle';
  const runOutput = nodeData._runOutput as any;
  const running = runStatus === 'running';

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
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        {entry.icon}
        <span style={{ fontWeight: 600, fontSize: 15 }}>{entry.label} 节点</span>
      </div>

      {/* Node type specific fields */}
      <div style={{ marginBottom: 16 }}>
        {nodeType === 'excel' && (
          <>
            <FieldInput label="P4 文件路径" value={(nodeData.p4Path as string) || ''} onChange={(v) => handleFieldChange('p4Path', v)} placeholder="P4 文件路径" />
            <FieldInput label="工作表名（可选）" value={(nodeData.sheet as string) || ''} onChange={(v) => handleFieldChange('sheet', v)} placeholder="工作表名" />
          </>
        )}
        {nodeType === 'lua' && (
          <>
            <FieldInput label="P4 文件路径" value={(nodeData.p4Path as string) || ''} onChange={(v) => handleFieldChange('p4Path', v)} placeholder="P4 文件路径" />
            <FieldInput label="入口函数（可选）" value={(nodeData.entryFunction as string) || ''} onChange={(v) => handleFieldChange('entryFunction', v)} placeholder="入口函数名" />
          </>
        )}
        {nodeType === 'json' && (
          <>
            <FieldInput label="P4 文件路径" value={(nodeData.p4Path as string) || ''} onChange={(v) => handleFieldChange('p4Path', v)} placeholder="P4 文件路径" />
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

      {/* Run result from node data — shows the selected node's own result */}
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

export default PropertyPanel;
