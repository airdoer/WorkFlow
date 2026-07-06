import React, { useState } from 'react';
import type { Node } from 'reactflow';
import { getNodeRegistry } from './NodeRegistry';
import { Button, message } from 'antd';
import { FlowApi } from './services/FlowApi';

interface PropertyPanelProps {
  selectedNode: Node | null;
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
}

const PropertyPanel: React.FC<PropertyPanelProps> = ({ selectedNode, setNodes }) => {
  const [running, setRunning] = useState(false);

  if (!selectedNode) {
    return (
      <div
        style={{
          width: 280,
          borderLeft: '1px solid #e8e8e8',
          padding: 16,
          background: '#fafafa',
        }}
      >
        <div style={{ color: '#999' }}>选择节点查看属性</div>
      </div>
    );
  }

  const nodeType = selectedNode.type ?? '';
  const nodeData = (selectedNode.data || {}) as Record<string, unknown>;
  const entry = getNodeRegistry(nodeType);

  if (!entry) {
    return (
      <div
        style={{
          width: 280,
          borderLeft: '1px solid #e8e8e8',
          padding: 16,
          background: '#fafafa',
        }}
      >
        <div style={{ color: '#999' }}>未知节点类型: {nodeType}</div>
      </div>
    );
  }

  const handleRunNode = async () => {
    setRunning(true);
    try {
      const result = await FlowApi.runNode(nodeType ?? '', nodeData, {});
      message.success('节点运行完成');
      console.log('Node output:', result);
    } catch (err: any) {
      message.error(`运行失败: ${err.message}`);
    } finally {
      setRunning(false);
    }
  };

  const handleFieldChange = (fieldName: string, value: any) => {
    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedNode.id
          ? { ...n, data: { ...n.data, [fieldName]: value } }
          : n,
      ),
    );
  };

  return (
    <div
      style={{
        width: 280,
        borderLeft: '1px solid #e8e8e8',
        padding: 16,
        background: '#fff',
        overflowY: 'auto',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        {entry.icon}
        <span style={{ fontWeight: 600, fontSize: 15 }}>{entry.label} 节点</span>
      </div>

      <div style={{ marginBottom: 16 }}>
        {nodeType === 'excel' && (
          <>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: '#666' }}>
                P4 文件路径
              </label>
              <input
                type="text"
                value={(nodeData.p4Path as string) || ''}
                onChange={(e) => handleFieldChange('p4Path', e.target.value)}
                placeholder="P4 文件路径"
                style={{ width: '100%', padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 2 }}
              />
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: '#666' }}>
                工作表名（可选）
              </label>
              <input
                type="text"
                value={(nodeData.sheet as string) || ''}
                onChange={(e) => handleFieldChange('sheet', e.target.value)}
                placeholder="工作表名"
                style={{ width: '100%', padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 2 }}
              />
            </div>
          </>
        )}
        {nodeType === 'lua' && (
          <>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: '#666' }}>
                P4 文件路径
              </label>
              <input
                type="text"
                value={(nodeData.p4Path as string) || ''}
                onChange={(e) => handleFieldChange('p4Path', e.target.value)}
                placeholder="P4 文件路径"
                style={{ width: '100%', padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 2 }}
              />
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: '#666' }}>
                入口函数（可选）
              </label>
              <input
                type="text"
                value={(nodeData.entryFunction as string) || ''}
                onChange={(e) => handleFieldChange('entryFunction', e.target.value)}
                placeholder="入口函数名"
                style={{ width: '100%', padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 2 }}
              />
            </div>
          </>
        )}
        {nodeType === 'json' && (
          <>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: '#666' }}>
                P4 文件路径
              </label>
              <input
                type="text"
                value={(nodeData.p4Path as string) || ''}
                onChange={(e) => handleFieldChange('p4Path', e.target.value)}
                placeholder="P4 文件路径"
                style={{ width: '100%', padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 2 }}
              />
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: '#666' }}>
                JSON Path（可选）
              </label>
              <input
                type="text"
                value={(nodeData.jsonPath as string) || ''}
                onChange={(e) => handleFieldChange('jsonPath', e.target.value)}
                placeholder="如 $.data.items"
                style={{ width: '100%', padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 2 }}
              />
            </div>
          </>
        )}
        {nodeType === 'prompt' && (
          <>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: '#666' }}>
                提示词
              </label>
              <textarea
                value={(nodeData.prompt as string) || ''}
                onChange={(e) => handleFieldChange('prompt', e.target.value)}
                placeholder="输入提示词，支持 {{nodeId.outputKey}} 变量"
                rows={6}
                style={{ width: '100%', padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 2, resize: 'vertical' }}
              />
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: '#666' }}>
                模型
              </label>
              <input
                type="text"
                value={(nodeData.model as string) || 'qwen-plus'}
                onChange={(e) => handleFieldChange('model', e.target.value)}
                placeholder="模型名称"
                style={{ width: '100%', padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 2 }}
              />
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: '#666' }}>
                温度
              </label>
              <input
                type="number"
                value={(nodeData.temperature as number) || 0.7}
                onChange={(e) => handleFieldChange('temperature', parseFloat(e.target.value))}
                placeholder="0.0 - 1.0"
                step="0.1"
                min="0"
                max="1"
                style={{ width: '100%', padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 2 }}
              />
            </div>
          </>
        )}
      </div>

      <Button type="primary" loading={running} onClick={handleRunNode} block>
        运行节点
      </Button>
    </div>
  );
};

export default PropertyPanel;
