import React, { useState } from 'react';
import { useNodeRender } from '@flowgram.ai/free-layout-editor';
import { getNodeRegistry } from './NodeRegistry';
import { Button, message } from 'antd';
import { FlowApi } from './services/FlowApi';

const PropertyPanel: React.FC = () => {
  const { formData, nodeType, nodeData } = useNodeRender();
  const [running, setRunning] = useState(false);
  const entry = getNodeRegistry(nodeType);

  if (!entry) {
    return (
      <div style={{ width: 280, borderLeft: '1px solid #e8e8e8', padding: 16, background: '#fafafa' }}>
        <div style={{ color: '#999' }}>选择节点查看属性</div>
      </div>
    );
  }

  const handleRunNode = async () => {
    setRunning(true);
    try {
      const result = await FlowApi.runNode(nodeType, nodeData, {});
      message.success('节点运行完成');
      console.log('Node output:', result);
    } catch (err: any) {
      message.error(`运行失败: ${err.message}`);
    } finally {
      setRunning(false);
    }
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
        {entry.registry.formMeta?.render?.({ form: formData } as any)}
      </div>

      <Button type="primary" loading={running} onClick={handleRunNode} block>
        运行节点
      </Button>
    </div>
  );
};

export default PropertyPanel;
